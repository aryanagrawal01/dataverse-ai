"""Forecast eligibility and time-series preparation."""

import pandas as pd

from dataverse.core.dashboard.semantics import (
    ensure_datetime,
    ensure_numeric,
    pick_date_column,
    pick_time_frequency,
    rank_metrics,
)
from dataverse.schemas.forecast import ForecastEligibility
from dataverse.schemas.profiling import DatasetProfile

_MIN_OBSERVATIONS = 12  # aggregated periods needed to fit anything honest


def check_eligibility(df: pd.DataFrame, profile: DatasetProfile) -> ForecastEligibility:
    date_col = pick_date_column(profile, df)
    if date_col is None:
        return ForecastEligibility(
            eligible=False,
            reason=(
                "Forecasting needs a date column, and none was detected in this "
                "dataset. If dates are stored as text, apply cleaning first."
            ),
        )
    metrics = [m for m in rank_metrics(profile) if m in df.columns]
    if not metrics:
        return ForecastEligibility(
            eligible=False,
            reason="Forecasting needs a numeric metric column (revenue, quantity, …).",
            date_column=date_col,
        )

    series = prepare_series(df, date_col, metrics[0])
    if len(series) < _MIN_OBSERVATIONS:
        return ForecastEligibility(
            eligible=False,
            reason=(
                f"Only {len(series)} usable time periods found after aggregation — "
                f"at least {_MIN_OBSERVATIONS} are needed for a trustworthy forecast."
            ),
            date_column=date_col,
            observations=len(series),
        )

    return ForecastEligibility(
        eligible=True,
        date_column=date_col,
        metric_options=metrics,
        frequency=_freq_for(df, date_col),
        observations=len(series),
    )


def _freq_for(df: pd.DataFrame, date_col: str) -> str:
    dates = ensure_datetime(df[date_col]).dropna()
    span = float((dates.max() - dates.min()).days) if len(dates) else 0.0
    return pick_time_frequency(span)[0]


def prepare_series(df: pd.DataFrame, date_col: str, metric: str) -> pd.Series:
    """Aggregate to a regular frequency, fill internal gaps with 0 (no activity).

    Partial edge buckets (an incomplete first/last week or month) are dropped —
    they read as artificial dips and would poison both backtests and intervals.
    """
    dates = ensure_datetime(df[date_col])
    values = ensure_numeric(df[metric])
    frame = pd.DataFrame({"d": dates, "v": values}).dropna()
    if frame.empty:
        return pd.Series(dtype="float64")
    freq = _freq_for(df, date_col)
    series = frame.set_index("d").resample(freq)["v"].sum().fillna(0.0)

    if freq in ("W", "ME") and len(series) >= 3:
        # Resample labels are bucket END dates.
        if frame["d"].max().normalize() < series.index[-1].normalize():
            series = series.iloc[:-1]
        first_end = series.index[0]
        first_start = first_end - pd.Timedelta(days=6) if freq == "W" else first_end.replace(day=1)
        if frame["d"].min().normalize() > first_start.normalize():
            series = series.iloc[1:]
    return series


def seasonal_period(freq: str) -> int:
    return {"D": 7, "W": 52, "ME": 12}.get(freq, 7)
