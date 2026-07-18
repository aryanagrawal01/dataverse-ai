"""Insight DTOs. FactPack carries every number the narrator may cite."""

from typing import Literal

from pydantic import BaseModel, Field

InsightKind = Literal["executive_summary", "trend", "segment", "anomaly", "recommendation"]


class MetricFacts(BaseModel):
    name: str
    total: float
    mean: float
    growth_pct: float | None = None  # second half vs first half of the date range
    best_period: str | None = None
    best_period_value: float | None = None
    worst_period: str | None = None
    worst_period_value: float | None = None


class SegmentFacts(BaseModel):
    dimension: str
    metric: str
    top_name: str
    top_value: float
    top_share_pct: float
    bottom_name: str
    bottom_value: float
    segments_count: int


class AnomalyFacts(BaseModel):
    column: str
    outlier_count: int
    outlier_pct: float
    example_high: float | None = None
    example_low: float | None = None


class FactPack(BaseModel):
    row_count: int
    column_count: int
    date_column: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    metrics: list[MetricFacts] = Field(default_factory=list)
    segments: list[SegmentFacts] = Field(default_factory=list)
    anomalies: list[AnomalyFacts] = Field(default_factory=list)
    health_score: int | None = None
    data_notes: list[str] = Field(default_factory=list)  # quality caveats


class InsightItem(BaseModel):
    kind: InsightKind
    title: str
    content: str


class InsightSet(BaseModel):
    items: list[InsightItem]
    model_used: str  # LLM model name or "template"
    facts: FactPack
