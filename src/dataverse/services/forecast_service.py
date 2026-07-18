"""Forecast orchestration: eligibility, run, persist, AI narrative."""

from dataverse.config import get_settings
from dataverse.core.forecasting import check_eligibility, prepare_series, run_forecast
from dataverse.core.profiling import profile_dataframe
from dataverse.llm import make_provider
from dataverse.models import Forecast
from dataverse.repositories.base import session_scope
from dataverse.schemas.forecast import ForecastEligibility, ForecastRequest, ForecastResult
from dataverse.services import llm_budget, pipeline_service
from dataverse.utils.errors import (
    BudgetExceededError,
    ForecastNotApplicableError,
    LLMError,
    ValidationError,
)
from dataverse.utils.logging import get_logger

log = get_logger(__name__)


def eligibility(user_id: str, project_id: str) -> ForecastEligibility:
    if not get_settings().enable_forecasting:
        return ForecastEligibility(
            eligible=False, reason="Forecasting is disabled on this deployment."
        )
    df = pipeline_service.load_dataframe(user_id, project_id, kind="best")
    profile = (
        pipeline_service.get_stored_profile(user_id, project_id, "cleaned")
        or pipeline_service.get_stored_profile(user_id, project_id, "raw")
        or profile_dataframe(df)
    )
    return check_eligibility(df, profile)


def run(user_id: str, project_id: str, request: ForecastRequest) -> ForecastResult:
    info = eligibility(user_id, project_id)
    if not info.eligible:
        raise ForecastNotApplicableError(
            f"not eligible: {info.reason}", user_message=info.reason or ""
        )
    if request.metric not in info.metric_options:
        raise ValidationError(
            f"metric {request.metric!r} not forecastable",
            user_message="Pick one of the suggested metric columns.",
        )

    df = pipeline_service.load_dataframe(user_id, project_id, kind="best")
    series = prepare_series(df, info.date_column or "", request.metric)
    result = run_forecast(series, request.metric, request.horizon, info.frequency or "D")
    result.narrative = _narrative(user_id, project_id, result)

    with session_scope() as s:
        s.add(
            Forecast(
                project_id=project_id,
                metric_column=result.metric,
                frequency=result.frequency,
                horizon=request.horizon,
                model_name=result.model_name,
                backtest_mape=result.backtest_mape,
                result_json=result.model_dump(mode="json"),
            )
        )
    log.info(
        "forecast.completed",
        project_id=project_id,
        metric=result.metric,
        model=result.model_name,
        mape=result.backtest_mape,
    )
    return result


def _narrative(user_id: str, project_id: str, result: ForecastResult) -> str:
    total_forecast = sum(b.mean for b in result.forecast)
    recent = [p.value for p in result.history[-len(result.forecast) :]]
    total_recent = sum(recent) if recent else 0.0
    change_pct = (
        round((total_forecast - total_recent) / abs(total_recent) * 100, 1)
        if total_recent
        else None
    )
    accuracy = (
        f"Backtest error is ±{result.backtest_mape:.0f}% (typical)."
        if result.backtest_mape is not None
        else "Accuracy could not be estimated on a holdout."
    )
    template = (
        f"The {result.metric} forecast for the next {len(result.forecast)} periods totals "
        f"{total_forecast:,.0f}"
        + (
            f", {'+' if change_pct >= 0 else ''}{change_pct}% versus the most recent "
            "equivalent period"
            if change_pct is not None
            else ""
        )
        + f". Model: {result.model_name.replace('_', ' ')} (chosen by backtest). {accuracy}"
    )

    provider = make_provider()
    if not provider.available:
        return template
    try:
        llm_budget.check_budget(project_id)
        llm_result = provider.complete(
            "You are a business analyst. Rewrite this forecast summary in 2-3 crisp, "
            "plain-language sentences for an executive. Keep every number exactly as given.",
            template,
            max_tokens=200,
        )
        llm_budget.record_usage(user_id, project_id, "forecast_narrative", provider.tracker)
        return llm_result.text.strip() or template
    except (LLMError, BudgetExceededError):
        return template
