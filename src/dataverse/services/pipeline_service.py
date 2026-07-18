"""Profiling pipeline: load stored data, profile it, persist results."""

import time

import pandas as pd

from dataverse.config.constants import (
    DATASET_KIND_CLEANED,
    DATASET_KIND_RAW,
    PROJECT_STATUS_CLEANED,
    PROJECT_STATUS_PROFILED,
)
from dataverse.core.cleaning import execute_plan, suggest_cleaning
from dataverse.core.profiling import profile_dataframe
from dataverse.models import CleaningLog, DatasetVersion
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.cleaning import (
    BeforeAfter,
    CleaningLogEntry,
    CleaningPlan,
    CleaningResult,
    CleaningSuggestion,
)
from dataverse.schemas.profiling import DatasetProfile
from dataverse.storage import get_storage
from dataverse.utils.dataframe import from_parquet_bytes, to_parquet_bytes
from dataverse.utils.errors import NotFoundError, ProfilingError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)


def load_dataframe(user_id: str, project_id: str, kind: str = DATASET_KIND_RAW) -> pd.DataFrame:
    """Load a stored dataset version. Prefers cleaned when kind='best'."""
    with session_scope() as s:
        repo = ProjectRepository(s)
        if repo.by_id_for_user(user_id, project_id) is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        if kind == "best":
            version = repo.version_by_kind(
                project_id, DATASET_KIND_CLEANED
            ) or repo.version_by_kind(project_id, DATASET_KIND_RAW)
        else:
            version = repo.version_by_kind(project_id, kind)
        if version is None:
            raise NotFoundError(f"no {kind} version for project {project_id}")
        key = version.storage_key
    return from_parquet_bytes(get_storage().get(key))


def profile_project(user_id: str, project_id: str) -> DatasetProfile:
    """Profile the raw version, persist profile_json + health score."""
    started = time.monotonic()
    df = load_dataframe(user_id, project_id, DATASET_KIND_RAW)
    try:
        profile = profile_dataframe(df)
    except Exception as exc:
        raise ProfilingError(f"profiler crashed: {type(exc).__name__}: {exc}") from exc

    with session_scope() as s:
        repo = ProjectRepository(s)
        project = repo.by_id_for_user(user_id, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} vanished during profiling")
        version = repo.version_by_kind(project_id, DATASET_KIND_RAW)
        if version is None:
            raise NotFoundError(f"raw version missing for {project_id}")
        version.profile_json = profile.model_dump(mode="json")
        project.health_score = profile.health.score
        project.status = PROJECT_STATUS_PROFILED

    log.info(
        "pipeline.profile_completed",
        project_id=project_id,
        rows=profile.row_count,
        duration_ms=int((time.monotonic() - started) * 1000),
        health=profile.health.score,
    )
    return profile


def suggest_cleaning_for_project(user_id: str, project_id: str) -> list[CleaningSuggestion]:
    profile = get_stored_profile(user_id, project_id)
    if profile is None:
        profile = profile_project(user_id, project_id)
    return suggest_cleaning(profile)


def apply_cleaning(user_id: str, project_id: str, plan: CleaningPlan) -> CleaningResult:
    """All-or-nothing: on any failure nothing is persisted and the project
    stays at its previous status."""
    started = time.monotonic()
    df = load_dataframe(user_id, project_id, DATASET_KIND_RAW)
    profile_before = get_stored_profile(user_id, project_id) or profile_dataframe(df)

    cleaned, log_entries = execute_plan(df, plan)  # raises CleaningError on failure
    profile_after = profile_dataframe(cleaned)
    parquet = to_parquet_bytes(cleaned)

    storage = get_storage()
    key = None
    with session_scope() as s:
        repo = ProjectRepository(s)
        project = repo.by_id_for_user(user_id, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")

        version = repo.version_by_kind(project_id, DATASET_KIND_CLEANED)
        if version is None:
            key = f"{user_id}/{project_id}/cleaned.parquet"
            version = DatasetVersion(
                project_id=project_id, kind=DATASET_KIND_CLEANED, storage_key=key
            )
            s.add(version)
        else:
            key = version.storage_key
        storage.put(key, parquet)
        version.row_count = len(cleaned)
        version.size_bytes = len(parquet)
        version.profile_json = profile_after.model_dump(mode="json")

        for entry in log_entries:
            s.add(
                CleaningLog(
                    project_id=project_id,
                    rule_name=entry.rule,
                    column_name=entry.column,
                    params_json=entry.params,
                    rows_affected=entry.rows_affected,
                    detail=entry.detail,
                )
            )

        project.status = PROJECT_STATUS_CLEANED
        project.health_score = profile_after.health.score
        project.row_count = len(cleaned)
        project.column_count = len(cleaned.columns)

    result = CleaningResult(
        log=log_entries,
        comparison=BeforeAfter(
            rows_before=profile_before.row_count,
            rows_after=profile_after.row_count,
            missing_cells_before=sum(c.missing_count for c in profile_before.columns),
            missing_cells_after=sum(c.missing_count for c in profile_after.columns),
            duplicate_rows_before=profile_before.duplicate_row_count,
            duplicate_rows_after=profile_after.duplicate_row_count,
            health_before=profile_before.health.score,
            health_after=profile_after.health.score,
        ),
    )
    log.info(
        "cleaning.applied",
        project_id=project_id,
        rules=len(log_entries),
        rows_after=profile_after.row_count,
        duration_ms=int((time.monotonic() - started) * 1000),
        health_after=profile_after.health.score,
    )
    return result


def get_cleaning_log(user_id: str, project_id: str) -> list[CleaningLogEntry]:
    with session_scope() as s:
        repo = ProjectRepository(s)
        if repo.by_id_for_user(user_id, project_id) is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        rows = (
            s.query(CleaningLog)
            .filter(CleaningLog.project_id == project_id)
            .order_by(CleaningLog.created_at)
            .all()
        )
        return [
            CleaningLogEntry(
                rule=r.rule_name,  # type: ignore[arg-type]
                column=r.column_name,
                params=r.params_json,
                rows_affected=r.rows_affected,
                detail=r.detail,
            )
            for r in rows
        ]


def export_csv(user_id: str, project_id: str) -> bytes:
    """Cleaned dataset (or raw if never cleaned) as UTF-8 CSV bytes."""
    df = load_dataframe(user_id, project_id, kind="best")
    return df.to_csv(index=False).encode("utf-8-sig")


def get_stored_profile(
    user_id: str, project_id: str, kind: str = DATASET_KIND_RAW
) -> DatasetProfile | None:
    with session_scope() as s:
        repo = ProjectRepository(s)
        if repo.by_id_for_user(user_id, project_id) is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        version = repo.version_by_kind(project_id, kind)
        if version is None or version.profile_json is None:
            return None
        return DatasetProfile.model_validate(version.profile_json)
