"""Cleaning DTOs: suggestions offered to the user, the accepted plan, results."""

from typing import Any, Literal

from pydantic import BaseModel, Field

RuleName = Literal[
    "deduplicate",
    "coerce_type",
    "impute_missing",
    "handle_outliers",
    "drop_constant_column",
]

ImputeStrategy = Literal["median", "mean", "zero", "mode", "unknown_label", "drop_rows"]
OutlierStrategy = Literal["keep", "cap", "remove_rows"]


class CleaningSuggestion(BaseModel):
    id: str  # stable within a profile, e.g. "impute_missing:revenue"
    rule: RuleName
    column: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    title: str  # short UI label
    description: str  # why we suggest it
    estimated_rows: int
    enabled_by_default: bool = True
    strategy_options: list[str] = Field(default_factory=list)  # user-selectable


class PlanItem(BaseModel):
    rule: RuleName
    column: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class CleaningPlan(BaseModel):
    items: list[PlanItem]


class CleaningLogEntry(BaseModel):
    rule: RuleName
    column: str | None
    params: dict[str, Any]
    rows_affected: int
    detail: str


class BeforeAfter(BaseModel):
    rows_before: int
    rows_after: int
    missing_cells_before: int
    missing_cells_after: int
    duplicate_rows_before: int
    duplicate_rows_after: int
    health_before: int
    health_after: int


class CleaningResult(BaseModel):
    log: list[CleaningLogEntry]
    comparison: BeforeAfter
