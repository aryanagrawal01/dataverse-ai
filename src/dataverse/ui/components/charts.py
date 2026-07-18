"""Streamlit chart rendering — thin wrappers over core figure builders."""

import streamlit as st

from dataverse.core.dashboard import figures
from dataverse.schemas.dashboard import ChartSpec
from dataverse.schemas.forecast import ForecastResult
from dataverse.schemas.profiling import CorrelationMatrix


def render_chart(spec: ChartSpec) -> None:
    st.plotly_chart(figures.build_figure(spec), use_container_width=True)


def render_correlation_heatmap(matrix: CorrelationMatrix) -> None:
    st.plotly_chart(figures.correlation_heatmap(matrix), use_container_width=True)


def render_missing_bar(names: list[str], pcts: list[float]) -> None:
    st.plotly_chart(figures.missing_bar(names, pcts), use_container_width=True)


def render_forecast(result: ForecastResult) -> None:
    st.plotly_chart(figures.forecast_figure(result), use_container_width=True)
