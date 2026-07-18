"""Forecasting DTOs."""

from pydantic import BaseModel, Field


class ForecastEligibility(BaseModel):
    eligible: bool
    reason: str | None = None  # user-facing when not eligible
    date_column: str | None = None
    metric_options: list[str] = Field(default_factory=list)
    frequency: str | None = None  # D | W | ME
    observations: int = 0


class ForecastRequest(BaseModel):
    metric: str
    horizon: int = Field(default=30, ge=2, le=365)  # periods, not days


class ForecastPoint(BaseModel):
    period: str
    value: float


class ForecastBand(BaseModel):
    period: str
    mean: float
    lo80: float
    hi80: float
    lo95: float
    hi95: float


class ForecastResult(BaseModel):
    metric: str
    frequency: str
    model_name: str  # 'seasonal_naive' | 'holt_winters'
    backtest_mape: float | None  # None when holdout too small
    history: list[ForecastPoint]
    forecast: list[ForecastBand]
    narrative: str | None = None
