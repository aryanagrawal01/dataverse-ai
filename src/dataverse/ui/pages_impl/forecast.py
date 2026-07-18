"""Forecast page: metric/horizon picker, forecast chart with intervals."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.schemas.forecast import ForecastRequest
from dataverse.services import forecast_service
from dataverse.ui.components import charts
from dataverse.ui.components.empty_states import hero
from dataverse.utils.errors import DataVerseError

_HORIZONS = {"D": [14, 30, 60, 90], "W": [4, 8, 13, 26], "ME": [3, 6, 12]}
_FREQ_LABEL = {"D": "days", "W": "weeks", "ME": "months"}


def render(user: UserDTO, project_id: str) -> None:
    try:
        info = forecast_service.eligibility(user.id, project_id)
    except DataVerseError as exc:
        st.error(exc.user_message)
        return

    if not info.eligible:
        hero(
            badge="Forecasting",
            title="Forecasting isn't available for this dataset",
            subtitle=info.reason or "",
        )
        return

    freq = info.frequency or "D"
    col_metric, col_horizon, col_run = st.columns([2, 1.5, 1])
    with col_metric:
        metric = st.selectbox("Metric to forecast", info.metric_options)
    with col_horizon:
        horizon = st.selectbox(
            f"Horizon ({_FREQ_LABEL.get(freq, 'periods')})",
            _HORIZONS.get(freq, [12]),
            index=1 if len(_HORIZONS.get(freq, [])) > 1 else 0,
        )
    with col_run:
        st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        run = st.button("Forecast", type="primary", use_container_width=True)

    st.caption(
        f"Using {info.observations} {_FREQ_LABEL.get(freq, 'periods')} of history "
        f"(date column: `{info.date_column}`). Models compete on a backtest; "
        "the winner ships with honest error ranges."
    )

    if not run:
        return
    try:
        with st.spinner("Backtesting models and forecasting…"):
            result = forecast_service.run(
                user.id, project_id, ForecastRequest(metric=metric, horizon=int(horizon))
            )
    except DataVerseError as exc:
        st.error(exc.user_message)
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Model", result.model_name.replace("_", " ").title())
    m2.metric(
        "Typical error",
        f"±{result.backtest_mape:.0f}%" if result.backtest_mape is not None else "n/a",
        help="Mean absolute percentage error on held-out history",
    )
    m3.metric("Forecast total", f"{sum(b.mean for b in result.forecast):,.0f}")

    charts.render_forecast(result)

    if result.narrative:
        with st.container(border=True):
            st.markdown(f"💡 {result.narrative}")
