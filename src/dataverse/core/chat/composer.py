"""Compose the final answer: computed result + optional chart + prose.

The LLM only rephrases the computed result; the template fallback renders it
directly. Either way, every number shown was computed by the executor.
"""

import json

from dataverse.llm.provider import LLMProvider
from dataverse.schemas.chat import ChatAnswer, QueryPlan, QueryResult
from dataverse.schemas.dashboard import BarChart, ChartSpec, DonutChart, LineChart, Series
from dataverse.utils.errors import LLMError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_SYSTEM = """You are a data analyst answering a user's question.
You get the QUESTION, the executed QUERY RESULT (the ground truth), and context.
Write a concise answer (1-3 sentences) citing numbers from the result EXACTLY.
Never invent numbers. If the result is empty, say the data contains no match.
Plain text only, no markdown tables (the UI shows the data separately)."""


def compose_answer(
    question: str,
    plan: QueryPlan,
    result: QueryResult,
    provider: LLMProvider,
) -> ChatAnswer:
    chart = _chart_for(plan, result)
    text: str
    model_used = "template"

    if provider.available:
        try:
            llm_result = provider.complete(
                _SYSTEM,
                (
                    f"QUESTION: {question}\n\n"
                    f"QUERY RESULT (columns: {result.columns}):\n"
                    f"{json.dumps(result.rows[:25])}\n"
                    f"EXTRAS: {json.dumps(result.summary)}"
                ),
                max_tokens=300,
            )
            text = llm_result.text.strip()
            model_used = llm_result.usage.model
        except LLMError:
            log.warning("chat.composer_fallback")
            text = _template_answer(result)
    else:
        text = _template_answer(result)

    return ChatAnswer(text=text, plan=plan, result=result, chart=chart, model_used=model_used)


def _template_answer(result: QueryResult) -> str:
    if not result.rows:
        return "No matching data found for that question."
    if len(result.rows) == 1 and len(result.columns) <= 4:
        pairs = ", ".join(
            f"{col}: {val:,}"
            if isinstance(val, (int | float)) and val is not None
            else f"{col}: {val}"
            for col, val in zip(result.columns, result.rows[0], strict=True)
        )
        return f"Result — {pairs}."
    lead = result.rows[0]
    extras = ""
    if "delta_pct" in result.summary and result.summary["delta_pct"] is not None:
        extras = f" Change: {result.summary['delta_pct']:+.1f}%."
    if "pearson_r" in result.summary:
        extras = f" Correlation coefficient: {result.summary['pearson_r']}."
    return (
        f"Top result: {', '.join(str(v) for v in lead)} "
        f"(showing {len(result.rows)} rows below).{extras}"
    )


def _chart_for(plan: QueryPlan, result: QueryResult) -> ChartSpec | None:
    if plan.chart_hint == "none" or not result.rows or len(result.rows) < 2:
        return None
    try:
        if plan.chart_hint == "line" and len(result.columns) >= 2:
            xs = [str(r[0]) for r in result.rows]
            ys = [float(r[1]) if r[1] is not None else None for r in result.rows]
            return LineChart(
                title=result.columns[1],
                y_label=result.columns[1],
                series=[Series(name=result.columns[1], x=xs, y=ys)],
            )
        if plan.chart_hint == "bar" and len(result.columns) >= 2:
            return BarChart(
                title=f"{result.columns[1]} by {result.columns[0]}",
                categories=[str(r[0]) for r in result.rows],
                values=[float(r[1]) if r[1] is not None else 0.0 for r in result.rows],
                value_label=result.columns[1],
            )
        if plan.chart_hint == "donut" and len(result.columns) >= 2:
            return DonutChart(
                title=f"{result.columns[1]} share",
                labels=[str(r[0]) for r in result.rows],
                values=[float(r[1]) if r[1] is not None else 0.0 for r in result.rows],
            )
    except (TypeError, ValueError):
        return None
    return None
