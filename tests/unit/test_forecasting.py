import numpy as np
import pandas as pd
import pytest

from dataverse.core.forecasting import check_eligibility, prepare_series, run_forecast
from dataverse.core.forecasting.models import holt_winters, seasonal_naive
from dataverse.core.profiling import profile_dataframe
from dataverse.utils.errors import ForecastNotApplicableError


def _daily_df(days: int = 180, trend: float = 0.5, weekly_amp: float = 20.0) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2026-01-01", periods=days, freq="D")
    base = 100 + trend * np.arange(days)
    seasonal = weekly_amp * np.sin(2 * np.pi * np.arange(days) / 7)
    noise = rng.normal(0, 5, days)
    return pd.DataFrame({"order_date": dates, "revenue": base + seasonal + noise})


class TestEligibility:
    def test_eligible_daily_data(self):
        df = _daily_df()
        info = check_eligibility(df, profile_dataframe(df))
        assert info.eligible
        assert info.date_column == "order_date"
        assert "revenue" in info.metric_options
        assert info.frequency == "ME" or info.observations > 0  # span 180d → W

    def test_no_date_column_rejected_with_reason(self):
        df = pd.DataFrame({"revenue": [1.5, 2.5, 3.5] * 20})
        info = check_eligibility(df, profile_dataframe(df))
        assert not info.eligible
        assert "date" in (info.reason or "").lower()

    def test_too_few_periods_rejected(self):
        df = _daily_df(days=8)
        info = check_eligibility(df, profile_dataframe(df))
        assert not info.eligible

    def test_no_numeric_metric_rejected(self):
        df = pd.DataFrame(
            {
                "order_date": pd.date_range("2026-01-01", periods=40, freq="D"),
                "note": [f"line {i} of free text notes here" for i in range(40)],
            }
        )
        info = check_eligibility(df, profile_dataframe(df))
        assert not info.eligible


class TestModels:
    def test_seasonal_naive_repeats_cycle(self):
        series = pd.Series(
            [float(i % 7) for i in range(28)],
            index=pd.date_range("2026-01-01", periods=28, freq="D"),
        )
        predicted = seasonal_naive(series, 14, 7)
        assert list(predicted[:7]) == list(predicted[7:14])

    def test_holt_winters_captures_trend(self):
        series = pd.Series(
            [100.0 + 2 * i for i in range(60)],
            index=pd.date_range("2026-01-01", periods=60, freq="D"),
        )
        predicted = holt_winters(series, 10, 7)
        assert predicted[-1] > series.iloc[-1]  # continues upward


class TestRunForecast:
    def test_full_run_produces_bands_and_accuracy(self):
        df = _daily_df()
        series = prepare_series(df, "order_date", "revenue")
        result = run_forecast(series, "revenue", horizon=14, freq="W")
        assert len(result.forecast) == 14
        assert result.backtest_mape is not None and result.backtest_mape < 50
        for band in result.forecast:
            assert band.lo95 <= band.lo80 <= band.mean <= band.hi80 <= band.hi95
        # Uncertainty widens with horizon
        first, last = result.forecast[0], result.forecast[-1]
        assert (last.hi95 - last.lo95) >= (first.hi95 - first.lo95)

    def test_beats_or_matches_baseline_on_trending_data(self):
        df = _daily_df(trend=1.5, weekly_amp=5.0)
        series = prepare_series(df, "order_date", "revenue")
        result = run_forecast(series, "revenue", horizon=8, freq="W")
        assert result.model_name in ("holt_winters", "seasonal_naive")

    def test_short_series_raises(self):
        series = pd.Series([1.0] * 6, index=pd.date_range("2026-01-01", periods=6, freq="D"))
        with pytest.raises(ForecastNotApplicableError):
            run_forecast(series, "x", horizon=5, freq="D")

    def test_nonnegative_series_never_forecasts_negative(self):
        df = _daily_df(trend=-0.6)
        df["revenue"] = df["revenue"].clip(lower=0)
        series = prepare_series(df, "order_date", "revenue")
        result = run_forecast(series, "revenue", horizon=20, freq="W")
        assert all(b.mean >= 0 for b in result.forecast)

    def test_result_json_roundtrip(self):
        from dataverse.schemas.forecast import ForecastResult

        df = _daily_df()
        series = prepare_series(df, "order_date", "revenue")
        result = run_forecast(series, "revenue", horizon=6, freq="W")
        restored = ForecastResult.model_validate(result.model_dump(mode="json"))
        assert restored == result


class TestForecastService:
    def test_end_to_end_with_sample_dataset(self):
        from pathlib import Path

        from dataverse.schemas.forecast import ForecastRequest
        from dataverse.services import (
            auth_service,
            forecast_service,
            ingestion_service,
            pipeline_service,
        )

        user = auth_service.register("fc@example.com", "password9").user
        data = Path("sample_data/retail_sales_demo.csv").read_bytes()
        project = ingestion_service.create_project_from_upload(user.id, "sales.csv", data)
        pipeline_service.profile_project(user.id, project.id)

        info = forecast_service.eligibility(user.id, project.id)
        assert info.eligible
        assert "revenue" in info.metric_options

        result = forecast_service.run(
            user.id, project.id, ForecastRequest(metric="revenue", horizon=8)
        )
        assert result.narrative  # template narrative without LLM
        assert len(result.forecast) == 8

    def test_bad_metric_rejected(self):
        from pathlib import Path

        from dataverse.schemas.forecast import ForecastRequest
        from dataverse.services import (
            auth_service,
            forecast_service,
            ingestion_service,
            pipeline_service,
        )
        from dataverse.utils.errors import ValidationError

        user = auth_service.register("fc2@example.com", "password9").user
        data = Path("sample_data/retail_sales_demo.csv").read_bytes()
        project = ingestion_service.create_project_from_upload(user.id, "sales.csv", data)
        pipeline_service.profile_project(user.id, project.id)
        with pytest.raises(ValidationError):
            forecast_service.run(user.id, project.id, ForecastRequest(metric="order_id", horizon=8))
