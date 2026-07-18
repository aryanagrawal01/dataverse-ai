"""Question → QueryPlan via the LLM (schema + question only, never raw data)."""

import json

from dataverse.llm.provider import LLMProvider
from dataverse.schemas.chat import QueryPlan
from dataverse.schemas.profiling import DatasetProfile
from dataverse.utils.errors import PlanValidationError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_SYSTEM = """You translate business questions about a dataset into a JSON query plan.
You receive the dataset SCHEMA (column names, types, sample values) and a QUESTION.
Return ONLY a JSON object matching this spec:

{
 "operation": "aggregate" | "top_n" | "trend" | "compare_periods" | "describe" | "correlate" | "filter_rows",
 "metrics": [{"column": "<numeric column>", "agg": "sum"|"mean"|"median"|"min"|"max"|"count"|"nunique"}],
 "group_by": ["<categorical column>", ...],
 "filters": [{"column": "<col>", "op": "eq"|"ne"|"gt"|"gte"|"lt"|"lte"|"in"|"between"|"contains", "value": ...}],
 "date_column": "<datetime column or null>",
 "frequency": "D"|"W"|"ME"|null,
 "period_a": ["YYYY-MM-DD","YYYY-MM-DD"] or null,
 "period_b": ["YYYY-MM-DD","YYYY-MM-DD"] or null,
 "columns": ["<col>", ...],
 "sort_desc": true|false,
 "limit": <int 1-100>,
 "chart_hint": "bar"|"line"|"donut"|"none"
}

Rules:
- Use ONLY column names that appear in the schema, exactly as written.
- "which X had most Y" → aggregate grouped by X, metric Y sum, limit 10, chart_hint bar.
- "over time / monthly / trend" → trend with the date column, chart_hint line.
- "compare <period1> and <period2>" → compare_periods with ISO date ranges within the data's range.
- "average/typical" → agg mean. Counts of rows → agg count on any column.
- If the question CANNOT be answered from this schema (missing concept/column),
  return {"error": "<one short sentence why>"} instead."""


def plan_query(question: str, profile: DatasetProfile, provider: LLMProvider) -> QueryPlan:
    """Raises PlanValidationError (bad/unanswerable) or LLMUnavailableError."""
    schema = _schema_block(profile)
    user = f"SCHEMA:\n{schema}\n\nQUESTION: {question.strip()}"

    last_error: str | None = None
    for _attempt in range(2):
        result = provider.complete(_SYSTEM, user, json_mode=True, max_tokens=500)
        try:
            payload = json.loads(result.text)
        except json.JSONDecodeError:
            last_error = "model returned invalid JSON"
            continue
        if "error" in payload:
            raise PlanValidationError(
                f"model declined: {payload['error']}",
                user_message=str(payload["error"]),
            )
        try:
            return QueryPlan.model_validate(payload)
        except ValueError as exc:
            last_error = f"plan failed validation: {exc}"
            user = (
                f"SCHEMA:\n{schema}\n\nQUESTION: {question.strip()}\n\n"
                f"Your previous plan was invalid: {last_error}. Return a corrected JSON plan."
            )
    log.warning("chat.plan_invalid", error=last_error)
    raise PlanValidationError(f"no valid plan after retry: {last_error}")


def _schema_block(profile: DatasetProfile) -> str:
    lines = []
    for c in profile.columns:
        samples = ", ".join(c.sample_values[:3])
        extra = ""
        if c.semantic_type == "datetime" and c.min_date and c.max_date:
            extra = f" range {c.min_date[:10]}..{c.max_date[:10]}"
        lines.append(f"- {c.name} ({c.semantic_type}{extra}) e.g. {samples}")
    return "\n".join(lines)


def starter_questions(profile: DatasetProfile) -> list[str]:
    """Deterministic suggested questions derived from the schema."""
    from dataverse.core.dashboard.semantics import rank_dimensions, rank_metrics

    questions: list[str] = []
    metrics = rank_metrics(profile)
    dims = rank_dimensions(profile)
    dates = profile.datetime_columns
    if metrics and dims:
        questions.append(f"Which {dims[0]} had the highest total {metrics[0]}?")
    if metrics and dates:
        questions.append(f"Show the {metrics[0]} trend over time")
    if len(metrics) >= 2:
        questions.append(f"Is {metrics[0]} correlated with {metrics[1]}?")
    if metrics:
        questions.append(f"What is the average {metrics[0]}?")
    return questions[:4]
