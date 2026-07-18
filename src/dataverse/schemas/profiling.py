"""Profiling result DTOs. Stored as JSON on dataset_versions.profile_json."""

from typing import Literal

from pydantic import BaseModel

SemanticType = Literal["numeric", "categorical", "datetime", "text", "boolean", "id"]
IssueKind = Literal[
    "missing_values",
    "duplicate_rows",
    "wrong_type",
    "outliers",
    "constant_column",
    "high_cardinality",
    "invalid_records",
]
Severity = Literal["high", "medium", "low"]


class NumericStats(BaseModel):
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    q1: float | None = None
    q3: float | None = None
    skew: float | None = None


class ColumnProfile(BaseModel):
    name: str
    pandas_dtype: str
    semantic_type: SemanticType
    missing_count: int
    missing_pct: float
    unique_count: int
    sample_values: list[str]
    stats: NumericStats | None = None
    # For object columns that are really numeric/datetime/boolean in disguise:
    suggested_type: SemanticType | None = None
    parse_success_pct: float | None = None  # how much converts cleanly
    outlier_count_iqr: int = 0
    outlier_count_zscore: int = 0
    is_constant: bool = False
    # Datetime-specific
    min_date: str | None = None
    max_date: str | None = None


class CorrelationMatrix(BaseModel):
    method: Literal["pearson", "spearman"]
    columns: list[str]
    values: list[list[float | None]]


class HealthIssue(BaseModel):
    kind: IssueKind
    severity: Severity
    column: str | None = None
    description: str
    affected_rows: int
    penalty: float


class HealthScore(BaseModel):
    score: int  # 0-100
    issues: list[HealthIssue]


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    memory_bytes: int
    duplicate_row_count: int
    columns: list[ColumnProfile]
    correlations: list[CorrelationMatrix]
    multivariate_outlier_count: int = 0
    health: HealthScore

    def column(self, name: str) -> ColumnProfile:
        return next(c for c in self.columns if c.name == name)

    @property
    def datetime_columns(self) -> list[ColumnProfile]:
        return [c for c in self.columns if c.semantic_type == "datetime"]

    @property
    def numeric_columns(self) -> list[ColumnProfile]:
        return [c for c in self.columns if c.semantic_type == "numeric"]
