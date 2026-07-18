"""Backtest-driven model selection and interval construction.

The fancy model must beat the naive baseline on a holdout, or the baseline
ships. Intervals come from holdout residuals, widened by sqrt(h) — honest
about growing uncertainty.
"""

import numpy as np
import pandas as pd

from dataverse.core.forecasting.models import MODELS
from dataverse.core.forecasting.preparer import seasonal_period
from dataverse.schemas.forecast import ForecastBand, ForecastPoint, ForecastResult
from dataverse.utils.errors import ForecastNotApplicableError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)

_Z80 = 1.2816
_Z95 = 1.9600
_MAX_HISTORY_POINTS = 400


def run_forecast(series: pd.Series, metric: str, horizon: int, freq: str) -> ForecastResult:
    if len(series) < 12:
        raise ForecastNotApplicableError(f"series too short: {len(series)}")
    period = seasonal_period(freq)

    holdout = max(4, min(len(series) // 5, period))
    train, test = series.iloc[:-holdout], series.iloc[-holdout:]

    scores: dict[str, float] = {}
    residual_std: dict[str, float] = {}
    for name, fn in MODELS.items():
        try:
            predicted = fn(train, holdout, period)
        except Exception as exc:  # a model failing must never kill the feature
            log.warning("forecast.model_failed", model=name, error=str(exc))
            continue
        actual = test.to_numpy(dtype=float)
        residuals = actual - predicted
        denom = np.where(np.abs(actual) < 1e-9, np.nan, np.abs(actual))
        mape = float(np.nanmean(np.abs(residuals) / denom) * 100)
        scores[name] = mape if np.isfinite(mape) else float("inf")
        residual_std[name] = float(np.std(residuals)) or float(np.std(train) or 1.0)

    if not scores:
        raise ForecastNotApplicableError(
            "all models failed",
            user_message="No forecasting model could fit this data.",
        )

    best = min(scores, key=lambda k: scores[k])
    log.info("forecast.model_selected", model=best, scores=scores)

    # Refit best model on the full series for the real forecast.
    points = MODELS[best](series, horizon, period)
    points = np.maximum(points, 0.0) if (series >= 0).all() else points
    std = residual_std[best]

    future_index = pd.date_range(series.index[-1] + _one_step(freq), periods=horizon, freq=freq)
    bands = []
    for h, (ts, mean) in enumerate(zip(future_index, points, strict=True), start=1):
        width = std * float(np.sqrt(h))
        bands.append(
            ForecastBand(
                period=str(ts.date()),
                mean=round(float(mean), 2),
                lo80=round(float(mean - _Z80 * width), 2),
                hi80=round(float(mean + _Z80 * width), 2),
                lo95=round(float(mean - _Z95 * width), 2),
                hi95=round(float(mean + _Z95 * width), 2),
            )
        )

    tail = series.tail(_MAX_HISTORY_POINTS)
    history = [
        ForecastPoint(period=str(ts.date()), value=round(float(v), 2))
        for ts, v in zip(pd.DatetimeIndex(tail.index), tail.to_numpy(), strict=True)
    ]
    mape_out = scores[best] if np.isfinite(scores[best]) else None
    return ForecastResult(
        metric=metric,
        frequency=freq,
        model_name=best,
        backtest_mape=round(mape_out, 1) if mape_out is not None else None,
        history=history,
        forecast=bands,
    )


def _one_step(freq: str) -> pd.Timedelta | pd.offsets.BaseOffset:
    if freq == "D":
        return pd.Timedelta(days=1)
    if freq == "W":
        return pd.Timedelta(weeks=1)
    return pd.offsets.MonthEnd(1)
