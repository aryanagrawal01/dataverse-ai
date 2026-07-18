"""Single place where Plotly figures are built for the UI."""

import plotly.graph_objects as go
import streamlit as st

from dataverse.schemas.profiling import CorrelationMatrix

_FONT = {"family": "Inter, 'Segoe UI', sans-serif", "color": "#1A1D27"}
_GRID = "#E7E8EF"


def _base_layout(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 36, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=_FONT,
        xaxis={"gridcolor": _GRID},
        yaxis={"gridcolor": _GRID},
    )
    return fig


def render_correlation_heatmap(matrix: CorrelationMatrix) -> None:
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.columns,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=[[("" if v is None else f"{v:.2f}") for v in row] for row in matrix.values],
            texttemplate="%{text}",
            hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>",
        )
    )
    _base_layout(fig, height=max(340, 40 * len(matrix.columns) + 120))
    st.plotly_chart(fig, use_container_width=True)


def render_missing_bar(names: list[str], pcts: list[float]) -> None:
    fig = go.Figure(
        go.Bar(
            x=pcts,
            y=names,
            orientation="h",
            marker_color="#4F46E5",
            hovertemplate="%{y}: %{x:.1f}% missing<extra></extra>",
        )
    )
    fig.update_xaxes(title="% missing", range=[0, 100])
    _base_layout(fig, height=max(200, 28 * len(names) + 80))
    st.plotly_chart(fig, use_container_width=True)
