"""Chat DTOs: the constrained QueryPlan DSL and answers.

The LLM emits a QueryPlan as JSON; Pydantic validation + column checks make it
safe to execute. No generated code ever runs.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from dataverse.schemas.dashboard import ChartSpec

Operation = Literal[
    "aggregate",
    "top_n",
    "trend",
    "compare_periods",
    "describe",
    "correlate",
    "filter_rows",
]

Agg = Literal["sum", "mean", "median", "min", "max", "count", "nunique"]

FilterOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "between", "contains"]


class PlanFilter(BaseModel):
    column: str
    op: FilterOp
    value: Any


class PlanMetric(BaseModel):
    column: str
    agg: Agg = "sum"


class QueryPlan(BaseModel):
    operation: Operation
    metrics: list[PlanMetric] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    filters: list[PlanFilter] = Field(default_factory=list)
    date_column: str | None = None
    frequency: Literal["D", "W", "ME"] | None = None
    period_a: list[str] | None = None  # [from, to] ISO dates
    period_b: list[str] | None = None
    columns: list[str] = Field(default_factory=list)  # describe/correlate targets
    sort_desc: bool = True
    limit: int = Field(default=10, ge=1, le=100)
    chart_hint: Literal["bar", "line", "donut", "none"] = "none"


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]  # small: capped by executor
    summary: dict[str, Any] = Field(default_factory=dict)  # op-specific extras


class ChatAnswer(BaseModel):
    text: str
    plan: QueryPlan | None = None
    result: QueryResult | None = None
    chart: ChartSpec | None = None
    model_used: str = "template"


class ChatMessageDTO(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    plan: QueryPlan | None = None
    chart: ChartSpec | None = None
