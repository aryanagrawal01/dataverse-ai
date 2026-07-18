"""ChartSpec → Plotly figure builders (UI- and report-shared)."""

import plotly.graph_objects as go

from dataverse.schemas.dashboard import (
    BarChart,
    BoxChart,
    ChartSpec,
    DonutChart,
    HeatmapChart,
    HistogramChart,
    LineChart,
)
from dataverse.schemas.forecast import ForecastResult
from dataverse.schemas.profiling import CorrelationMatrix

_FONT = {"family": "Inter, 'Segoe UI', sans-serif", "color": "#1A1D27"}
_GRID = "#E7E8EF"
PRIMARY = "#4F46E5"
ACCENT = "#7C3AED"
PALETTE = ["#4F46E5", "#7C3AED", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#64748B", "#EC4899"]


def base_layout(fig: go.Figure, height: int = 380) -> go.Figure:
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


def build_figure(spec: ChartSpec) -> go.Figure:
    if isinstance(spec, LineChart):
        return _line(spec)
    if isinstance(spec, BarChart):
        return _bar(spec)
    if isinstance(spec, DonutChart):
        return _donut(spec)
    if isinstance(spec, HistogramChart):
        return _histogram(spec)
    if isinstance(spec, BoxChart):
        return _box(spec)
    if isinstance(spec, HeatmapChart):
        return correlation_heatmap(spec.matrix, title=spec.title)
    raise ValueError(f"unknown chart spec {type(spec)!r}")


def correlation_heatmap(matrix: CorrelationMatrix, title: str = "") -> go.Figure:
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
    fig.update_layout(title=title or None)
    return base_layout(fig, height=max(340, 40 * len(matrix.columns) + 120))


def missing_bar(names: list[str], pcts: list[float]) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=pcts,
            y=names,
            orientation="h",
            marker_color=PRIMARY,
            hovertemplate="%{y}: %{x:.1f}% missing<extra></extra>",
        )
    )
    fig.update_xaxes(title="% missing", range=[0, 100])
    return base_layout(fig, height=max(200, 28 * len(names) + 80))


def forecast_figure(result: ForecastResult) -> go.Figure:
    fig = go.Figure()
    hx = [p.period for p in result.history]
    hy = [p.value for p in result.history]
    fx = [b.period for b in result.forecast]

    fig.add_trace(
        go.Scatter(
            x=fx + fx[::-1],
            y=[b.hi95 for b in result.forecast] + [b.lo95 for b in result.forecast][::-1],
            fill="toself",
            fillcolor="rgba(79, 70, 229, 0.08)",
            line={"width": 0},
            name="95% range",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=fx + fx[::-1],
            y=[b.hi80 for b in result.forecast] + [b.lo80 for b in result.forecast][::-1],
            fill="toself",
            fillcolor="rgba(79, 70, 229, 0.16)",
            line={"width": 0},
            name="80% range",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(x=hx, y=hy, mode="lines", name="History", line={"color": "#1A1D27", "width": 2})
    )
    fig.add_trace(
        go.Scatter(
            x=fx,
            y=[b.mean for b in result.forecast],
            mode="lines",
            name="Forecast",
            line={"color": PRIMARY, "width": 2.5, "dash": "dash"},
        )
    )
    fig.update_layout(
        title=f"{result.metric} forecast ({result.model_name.replace('_', ' ')})",
        legend={"orientation": "h", "y": -0.15},
    )
    return base_layout(fig, height=440)


def _line(spec: LineChart) -> go.Figure:
    fig = go.Figure()
    for s in spec.series:
        fig.add_trace(
            go.Scatter(
                x=s.x,
                y=s.y,
                mode="lines",
                name=s.name,
                line={"color": PRIMARY, "width": 2.5},
                fill="tozeroy",
                fillcolor="rgba(79, 70, 229, 0.07)",
                hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
            )
        )
    fig.update_layout(title=spec.title, showlegend=len(spec.series) > 1)
    fig.update_yaxes(title=spec.y_label)
    return base_layout(fig)


def _bar(spec: BarChart) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=spec.values if spec.horizontal else spec.categories,
            y=spec.categories if spec.horizontal else spec.values,
            orientation="h" if spec.horizontal else "v",
            marker_color=PRIMARY,
            hovertemplate="%{y}: %{x:,.2f}<extra></extra>"
            if spec.horizontal
            else "%{x}: %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(title=spec.title)
    if spec.horizontal:
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title=spec.value_label)
    return base_layout(fig)


def _donut(spec: DonutChart) -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=spec.labels,
            values=spec.values,
            hole=0.55,
            marker={"colors": PALETTE[: len(spec.labels)]},
            textinfo="label+percent",
            hovertemplate="%{label}: %{value:,.2f} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(title=spec.title, showlegend=False)
    return base_layout(fig)


def _histogram(spec: HistogramChart) -> go.Figure:
    centers = [(spec.bin_edges[i] + spec.bin_edges[i + 1]) / 2 for i in range(len(spec.counts))]
    widths = [(spec.bin_edges[i + 1] - spec.bin_edges[i]) * 0.92 for i in range(len(spec.counts))]
    fig = go.Figure(
        go.Bar(
            x=centers,
            y=spec.counts,
            width=widths,
            marker_color=ACCENT,
            hovertemplate="%{y} rows<extra></extra>",
        )
    )
    fig.update_layout(title=spec.title, bargap=0)
    fig.update_xaxes(title=spec.x_label)
    fig.update_yaxes(title="rows")
    return base_layout(fig)


def _box(spec: BoxChart) -> go.Figure:
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
                marker_color=PRIMARY,
            )
        )
    fig.update_layout(title=spec.title, showlegend=False)
    fig.update_yaxes(title=spec.y_label)
    return base_layout(fig)
