"""Chat with data: plan → execute → compose → persist, with full audit trail."""

from typing import Any

from sqlalchemy import select

from dataverse.config import get_settings
from dataverse.core.chat import compose_answer, execute_query_plan, plan_query, starter_questions
from dataverse.core.profiling import profile_dataframe
from dataverse.llm import make_provider
from dataverse.models import ChatMessage
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.chat import ChatAnswer, ChatMessageDTO, QueryPlan
from dataverse.schemas.dashboard import (
    BarChart,
    ChartSpec,
    DonutChart,
    HeatmapChart,
    LineChart,
)
from dataverse.services import llm_budget, pipeline_service
from dataverse.utils.errors import ChatError, LLMUnavailableError, ValidationError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_MAX_QUESTION_CHARS = 500


def ask(user_id: str, project_id: str, question: str) -> ChatAnswer:
    question = question.strip()
    if not question or len(question) > _MAX_QUESTION_CHARS:
        raise ValidationError(
            f"question length {len(question)}",
            user_message=f"Questions must be 1–{_MAX_QUESTION_CHARS} characters.",
        )
    if not get_settings().enable_chat:
        raise ChatError("chat disabled", user_message="Chat is disabled on this deployment.")

    df = pipeline_service.load_dataframe(user_id, project_id, kind="best")
    profile = (
        pipeline_service.get_stored_profile(user_id, project_id, "cleaned")
        or pipeline_service.get_stored_profile(user_id, project_id, "raw")
        or profile_dataframe(df)
    )

    provider = make_provider()
    if not provider.available:
        raise LLMUnavailableError(
            "chat requires an LLM",
            user_message=(
                "Chat needs an AI key (OPENAI_API_KEY) configured. Dashboards, "
                "cleaning, and profiling all work without it."
            ),
        )
    llm_budget.check_budget(project_id)

    _persist(project_id, "user", question, None, None)
    try:
        plan = plan_query(question, profile, provider)
        result = execute_query_plan(df, plan)
        answer = compose_answer(question, plan, result, provider)
    except ChatError as exc:
        llm_budget.record_usage(user_id, project_id, "chat", provider.tracker)
        _persist(project_id, "assistant", exc.user_message, None, None)
        raise
    llm_budget.record_usage(user_id, project_id, "chat", provider.tracker)
    _persist(
        project_id,
        "assistant",
        answer.text,
        answer.plan.model_dump(mode="json") if answer.plan else None,
        answer.chart.model_dump(mode="json") if answer.chart else None,
    )
    log.info("chat.answered", project_id=project_id, operation=plan.operation)
    return answer


def history(user_id: str, project_id: str) -> list[ChatMessageDTO]:
    with session_scope() as s:
        repo = ProjectRepository(s)
        if repo.by_id_for_user(user_id, project_id) is None:
            from dataverse.utils.errors import NotFoundError

            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        rows = list(
            s.execute(
                select(ChatMessage)
                .where(ChatMessage.project_id == project_id)
                .order_by(ChatMessage.created_at)
            ).scalars()
        )
    return [
        ChatMessageDTO(
            role=r.role,  # type: ignore[arg-type]
            content=r.content,
            plan=QueryPlan.model_validate(r.query_plan_json) if r.query_plan_json else None,
            chart=_chart_from_json(r.chart_spec_json),
        )
        for r in rows
    ]


def suggested_questions(user_id: str, project_id: str) -> list[str]:
    profile = pipeline_service.get_stored_profile(
        user_id, project_id, "cleaned"
    ) or pipeline_service.get_stored_profile(user_id, project_id, "raw")
    if profile is None:
        return []
    return starter_questions(profile)


def _chart_from_json(raw: dict | None) -> ChartSpec | None:
    if raw is None:
        return None
    by_kind: dict[str, Any] = {
        "line": LineChart,
        "bar": BarChart,
        "donut": DonutChart,
        "heatmap": HeatmapChart,
    }
    cls = by_kind.get(raw.get("kind", ""))
    if cls is None:
        return None
    try:
        return cls.model_validate(raw)
    except ValueError:
        return None


def _persist(
    project_id: str, role: str, content: str, plan_json: dict | None, chart_json: dict | None
) -> None:
    with session_scope() as s:
        s.add(
            ChatMessage(
                project_id=project_id,
                role=role,
                content=content,
                query_plan_json=plan_json,
                chart_spec_json=chart_json,
            )
        )
