"""Dashboard DTOs: fully-computed specs the UI can render without pandas.

Chart data is embedded (small aggregates only), so specs are cacheable and
the UI layer stays free of analytics logic.
"""

from typing import Literal

from pydantic import BaseModel, Field

from dataverse.schemas.profiling import CorrelationMatrix


class KpiSpec(BaseModel):
    label: str
    value: str  # pre-formatted
    delta: str | None = None  # e.g. "+8.2% vs previous period"
    delta_positive: bool | None = None


class Series(BaseModel):
    name: str
    x: list[str]
    y: list[float | None]


class LineChart(BaseModel):
    kind: Literal["line"] = "line"
    title: str
    y_label: str
    series: list[Series]


class BarChart(BaseModel):
    kind: Literal["bar"] = "bar"
    title: str
    categories: list[str]
    values: list[float]
    value_label: str
    horizontal: bool = True


class DonutChart(BaseModel):
    kind: Literal["donut"] = "donut"
    title: str
    labels: list[str]
    values: list[float]


class HistogramChart(BaseModel):
    kind: Literal["histogram"] = "histogram"
    title: str
    bin_edges: list[float]
    counts: list[int]
    x_label: str


class BoxChart(BaseModel):
    kind: Literal["box"] = "box"
    title: str
    groups: list[str]
    # Precomputed five-number summaries per group: [min, q1, median, q3, max]
    summaries: list[list[float]]
    y_label: str


class HeatmapChart(BaseModel):
    kind: Literal["heatmap"] = "heatmap"
    title: str
    matrix: CorrelationMatrix


ChartSpec = LineChart | BarChart | DonutChart | HistogramChart | BoxChart | HeatmapChart


class FilterOptions(BaseModel):
    date_column: str | None = None
    date_min: str | None = None
    date_max: str | None = None
    category_column: str | None = None
    category_values: list[str] = Field(default_factory=list)


class DashboardFilters(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    categories: list[str] = Field(default_factory=list)


class DashboardSpec(BaseModel):
    kpis: list[KpiSpec]
    charts: list[ChartSpec]
    filter_options: FilterOptions
    dataset_kind: str  # 'raw' or 'cleaned' — shown as a badge
