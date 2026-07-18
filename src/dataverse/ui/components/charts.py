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


def render_chart(spec) -> None:
    """Dispatch a ChartSpec union member to its renderer."""
    from dataverse.schemas import dashboard as d

    if isinstance(spec, d.LineChart):
        _render_line(spec)
    elif isinstance(spec, d.BarChart):
        _render_bar(spec)
    elif isinstance(spec, d.DonutChart):
        _render_donut(spec)
    elif isinstance(spec, d.HistogramChart):
        _render_histogram(spec)
    elif isinstance(spec, d.BoxChart):
        _render_box(spec)
    elif isinstance(spec, d.HeatmapChart):
        st.markdown(f"**{spec.title}**")
        render_correlation_heatmap(spec.matrix)


def _render_line(spec) -> None:
    fig = go.Figure()
    for s in spec.series:
        fig.add_trace(
            go.Scatter(
                x=s.x,
                y=s.y,
                mode="lines",
                name=s.name,
                line={"color": "#4F46E5", "width": 2.5},
                fill="tozeroy",
                fillcolor="rgba(79, 70, 229, 0.07)",
                hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
            )
        )
    fig.update_layout(title=spec.title, showlegend=len(spec.series) > 1)
    fig.update_yaxes(title=spec.y_label)
    st.plotly_chart(_base_layout(fig), use_container_width=True)


def _render_bar(spec) -> None:
    fig = go.Figure(
        go.Bar(
            x=spec.values if spec.horizontal else spec.categories,
            y=spec.categories if spec.horizontal else spec.values,
            orientation="h" if spec.horizontal else "v",
            marker_color="#4F46E5",
            hovertemplate="%{y}: %{x:,.2f}<extra></extra>"
            if spec.horizontal
            else "%{x}: %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(title=spec.title)
    if spec.horizontal:
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title=spec.value_label)
    st.plotly_chart(_base_layout(fig), use_container_width=True)


def _render_donut(spec) -> None:
    palette = [
        "#4F46E5",
        "#7C3AED",
        "#0EA5E9",
        "#10B981",
        "#F59E0B",
        "#EF4444",
        "#64748B",
        "#EC4899",
    ]
    fig = go.Figure(
        go.Pie(
            labels=spec.labels,
            values=spec.values,
            hole=0.55,
            marker={"colors": palette[: len(spec.labels)]},
            textinfo="label+percent",
            hovertemplate="%{label}: %{value:,.2f} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(title=spec.title, showlegend=False)
    st.plotly_chart(_base_layout(fig), use_container_width=True)


def _render_histogram(spec) -> None:
    centers = [(spec.bin_edges[i] + spec.bin_edges[i + 1]) / 2 for i in range(len(spec.counts))]
    widths = [(spec.bin_edges[i + 1] - spec.bin_edges[i]) * 0.92 for i in range(len(spec.counts))]
    fig = go.Figure(
        go.Bar(
            x=centers,
            y=spec.counts,
            width=widths,
            marker_color="#7C3AED",
            hovertemplate="%{y} rows<extra></extra>",
        )
    )
    fig.update_layout(title=spec.title, bargap=0)
    fig.update_xaxes(title=spec.x_label)
    fig.update_yaxes(title="rows")
    st.plotly_chart(_base_layout(fig), use_container_width=True)


def _render_box(spec) -> None:
    fig = go.Figure()
    for group, (lo, q1, med, q3, hi) in zip(spec.groups, spec.summaries, strict=True):
        fig.add_trace(
            go.Box(
                name=group,
                lowerfence=[lo],
                q1=[q1],
                median=[med],
                q3=[q3],
                upperfence=[hi],
                marker_color="#4F46E5",
            )
        )
    fig.update_layout(title=spec.title, showlegend=False)
    fig.update_yaxes(title=spec.y_label)
    st.plotly_chart(_base_layout(fig), use_container_width=True)


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
