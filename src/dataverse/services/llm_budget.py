"""Per-project LLM budget enforcement and usage recording."""

from sqlalchemy import func, select

from dataverse.config import get_settings
from dataverse.llm.provider import UsageTracker
from dataverse.models import LLMUsageRecord
from dataverse.repositories.base import session_scope
from dataverse.utils.errors import BudgetExceededError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)


def spent_usd(project_id: str) -> float:
    with session_scope() as s:
        total = s.execute(
            select(func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0)).where(
                LLMUsageRecord.project_id == project_id
            )
        ).scalar_one()
    return float(total)


def check_budget(project_id: str) -> None:
    cap = get_settings().llm_budget_usd_per_project
    if cap <= 0:
        return
    if spent_usd(project_id) >= cap:
        log.warning("llm.budget_exhausted", project_id=project_id, cap_usd=cap)
        raise BudgetExceededError(f"project {project_id} reached LLM budget ${cap}")


def record_usage(user_id: str, project_id: str | None, feature: str, tracker: UsageTracker) -> None:
    if not tracker.calls:
        return
    with session_scope() as s:
        for u in tracker.calls:
            s.add(
                LLMUsageRecord(
                    user_id=user_id,
                    project_id=project_id,
                    feature=feature,
                    model=u.model,
                    prompt_tokens=u.prompt_tokens,
                    completion_tokens=u.completion_tokens,
                    cost_usd=u.cost_usd,
                )
            )
