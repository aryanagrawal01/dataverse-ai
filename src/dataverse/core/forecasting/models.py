"""Forecast models: seasonal-naive baseline and Holt-Winters.

Each model exposes fit_predict(train, horizon) -> point forecasts. Interval
estimation happens in the selector from backtest residuals — uniform and
honest across models.
"""

import numpy as np
import pandas as pd


def seasonal_naive(train: pd.Series, horizon: int, period: int) -> np.ndarray:
    """Repeat the last observed seasonal cycle (or last value when aseasonal)."""
    values = train.to_numpy(dtype=float)
    if len(values) >= period > 1:
        cycle = values[-period:]
        reps = int(np.ceil(horizon / period))
        return np.tile(cycle, reps)[:horizon]
    return np.full(horizon, values[-1] if len(values) else 0.0)


def holt_winters(train: pd.Series, horizon: int, period: int) -> np.ndarray:
    """Exponential smoothing with additive trend; seasonality when supported."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    use_seasonal = period > 1 and len(train) >= 2 * period
    model = ExponentialSmoothing(
        train.to_numpy(dtype=float),
        trend="add",
        damped_trend=True,
        seasonal="add" if use_seasonal else None,
        seasonal_periods=period if use_seasonal else None,
        initialization_method="estimated",
    )
    fitted = model.fit(optimized=True)
    return np.asarray(fitted.forecast(horizon), dtype=float)


MODELS = {
    "seasonal_naive": seasonal_naive,
    "holt_winters": holt_winters,
}
