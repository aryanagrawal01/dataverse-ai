"""Profiling pipeline: load stored data, profile it, persist results."""

import time

import pandas as pd

from dataverse.config.constants import (
    DATASET_KIND_CLEANED,
    DATASET_KIND_RAW,
    PROJECT_STATUS_PROFILED,
)
from dataverse.core.profiling import profile_dataframe
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.profiling import DatasetProfile
from dataverse.storage import get_storage
from dataverse.utils.dataframe import from_parquet_bytes
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
