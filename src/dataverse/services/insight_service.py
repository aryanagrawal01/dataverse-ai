"""AI insights: generation, per-dataset-version caching, budget enforcement."""

from sqlalchemy import select

from dataverse.config import get_settings
from dataverse.config.constants import DATASET_KIND_CLEANED, DATASET_KIND_RAW
from dataverse.core.insights import extract_facts, narrate
from dataverse.core.profiling import profile_dataframe
from dataverse.llm import make_provider
from dataverse.llm.null_provider import NullProvider
from dataverse.models import Insight
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.insights import FactPack, InsightItem, InsightSet
from dataverse.services import llm_budget, pipeline_service
from dataverse.utils.errors import BudgetExceededError, NotFoundError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)


def generate(user_id: str, project_id: str, force: bool = False) -> InsightSet:
    if not get_settings().enable_insights:
        raise NotFoundError("insights disabled", user_message="Insights are disabled.")

    version_id, kind = _best_version(user_id, project_id)
    if not force:
        cached = _cached(project_id, version_id)
        if cached is not None:
            return cached

    df = pipeline_service.load_dataframe(user_id, project_id, kind)
    profile = pipeline_service.get_stored_profile(user_id, project_id, kind) or profile_dataframe(
        df
    )
    facts = extract_facts(df, profile)

    provider = make_provider()
    if provider.available:
        try:
            llm_budget.check_budget(project_id)
        except BudgetExceededError:
            provider = NullProvider()

    insight_set = narrate(facts, provider)
    llm_budget.record_usage(user_id, project_id, "insights", provider.tracker)
    _store(project_id, version_id, insight_set)
    log.info(
        "insights.generated",
        project_id=project_id,
        items=len(insight_set.items),
        model=insight_set.model_used,
    )
    return insight_set


def _best_version(user_id: str, project_id: str) -> tuple[str, str]:
    with session_scope() as s:
        repo = ProjectRepository(s)
        if repo.by_id_for_user(user_id, project_id) is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        version = repo.version_by_kind(project_id, DATASET_KIND_CLEANED)
        kind = DATASET_KIND_CLEANED
        if version is None:
            version = repo.version_by_kind(project_id, DATASET_KIND_RAW)
            kind = DATASET_KIND_RAW
        if version is None:
            raise NotFoundError(f"no data versions for project {project_id}")
        return version.id, kind


def _cached(project_id: str, version_id: str) -> InsightSet | None:
    with session_scope() as s:
        rows = list(
            s.execute(
                select(Insight)
                .where(Insight.project_id == project_id, Insight.dataset_version_id == version_id)
                .order_by(Insight.created_at)
            ).scalars()
        )
        if not rows:
            return None
        facts = (
            FactPack.model_validate(rows[0].facts_json)
            if rows[0].facts_json
            else FactPack(row_count=0, column_count=0)
        )
        return InsightSet(
            items=[
                InsightItem(kind=r.kind, title=r.title, content=r.content)  # type: ignore[arg-type]
                for r in rows
            ],
            model_used=rows[0].model_used,
            facts=facts,
        )


def _store(project_id: str, version_id: str, insight_set: InsightSet) -> None:
    with session_scope() as s:
        # Replace any previous generation for this version (regenerate case).
        for old in s.execute(
            select(Insight).where(
                Insight.project_id == project_id, Insight.dataset_version_id == version_id
            )
        ).scalars():
            s.delete(old)
        facts_json = insight_set.facts.model_dump(mode="json")
        for i, item in enumerate(insight_set.items):
            s.add(
                Insight(
                    project_id=project_id,
                    dataset_version_id=version_id,
                    kind=item.kind,
                    title=item.title,
                    content=item.content,
                    facts_json=facts_json if i == 0 else None,
                    model_used=insight_set.model_used,
                )
            )
