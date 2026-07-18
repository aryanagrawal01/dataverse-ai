"""ChartSpec to PNG bytes for PDF reports, rendered with matplotlib (Agg).

Plotly + Kaleido was rejected for this path: Kaleido ships a headless Chromium
that hangs intermittently on some hosts (OneDrive-synced folders, locked-down
containers). Matplotlib is pure Python and deterministic, the right tool for
server-side static rendering. Plotly remains the interactive UI renderer.
"""

import io
from collections.abc import Callable
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, MaxNLocator

from dataverse.schemas.dashboard import (
    BarChart,
    BoxChart,
    ChartSpec,
    DonutChart,
    HistogramChart,
    LineChart,
)

PRIMARY = "#4F46E5"
ACCENT = "#7C3AED"
INK = "#1A1D27"
SOFT = "#5A6072"
BORDER = "#E7E8EF"
PALETTE = ["#4F46E5", "#7C3AED", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#64748B", "#EC4899"]

_FIGSIZE = (8.0, 4.0)
_DPI = 150


def render_png(spec: ChartSpec) -> bytes | None:
    """PNG bytes for a chart spec; None for kinds we don't render in PDFs."""
    if isinstance(spec, LineChart):
        return _render(_draw_line, spec)
    if isinstance(spec, BarChart):
        return _render(_draw_bar, spec)
    if isinstance(spec, DonutChart):
        return _render(_draw_donut, spec)
    if isinstance(spec, HistogramChart):
        return _render(_draw_histogram, spec)
    if isinstance(spec, BoxChart):
        return _render(_draw_box, spec)
    return None  # heatmaps render poorly at PDF scale


def _render(draw: Callable[[Axes, Any], None], spec: Any) -> bytes:
    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    try:
        draw(ax, spec)
        _style(ax, getattr(spec, "title", ""))
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor="white", bbox_inches="tight")
        return buf.getvalue()
    finally:
        plt.close(fig)


def _style(ax: Axes, title: str) -> None:
    ax.set_title(title, color=INK, fontsize=12, loc="left", pad=12)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BORDER)
    ax.tick_params(colors=SOFT, labelsize=8)
    ax.yaxis.grid(True, color=BORDER, linewidth=0.7)
    ax.set_axisbelow(True)


def _compact(v: float, _pos: object = None) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.0f}K"
    return f"{v:g}"


def _draw_line(ax: Axes, spec: LineChart) -> None:
    for s in spec.series:
        ys = [y if y is not None else float("nan") for y in s.y]
        ax.plot(s.x, ys, color=PRIMARY, linewidth=2)
        ax.fill_between(range(len(s.x)), ys, alpha=0.07, color=PRIMARY)
    ax.set_ylabel(spec.y_label, color=SOFT, fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(_compact))
    step = max(1, len(spec.series[0].x) // 8) if spec.series else 1
    ax.set_xticks(range(0, len(spec.series[0].x), step))
    ax.set_xticklabels(spec.series[0].x[::step], rotation=30, ha="right")


def _draw_bar(ax: Axes, spec: BarChart) -> None:
    positions = range(len(spec.categories))
    if spec.horizontal:
        ax.barh(positions, spec.values, color=PRIMARY, height=0.65)
        ax.set_yticks(positions)
        ax.set_yticklabels(spec.categories, fontsize=8)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(FuncFormatter(_compact))
        ax.set_xlabel(spec.value_label, color=SOFT, fontsize=9)
        ax.xaxis.grid(True, color=BORDER, linewidth=0.7)
        ax.yaxis.grid(False)
    else:
        ax.bar(positions, spec.values, color=PRIMARY, width=0.65)
        ax.set_xticks(positions)
        ax.set_xticklabels(spec.categories, rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(FuncFormatter(_compact))


def _draw_donut(ax: Axes, spec: DonutChart) -> None:
    total = sum(spec.values) or 1.0
    wedges, _texts, _autotexts = ax.pie(
        spec.values,
        labels=[
            f"{label} ({v / total * 100:.0f}%)"
            for label, v in zip(spec.labels, spec.values, strict=True)
        ],
        colors=PALETTE[: len(spec.labels)],
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        textprops={"color": INK, "fontsize": 8},
        autopct="",
        startangle=90,
    )
    ax.set_aspect("equal")
    ax.yaxis.grid(False)


def _draw_histogram(ax: Axes, spec: HistogramChart) -> None:
    centers = [(spec.bin_edges[i] + spec.bin_edges[i + 1]) / 2 for i in range(len(spec.counts))]
    widths = [(spec.bin_edges[i + 1] - spec.bin_edges[i]) * 0.92 for i in range(len(spec.counts))]
    ax.bar(centers, spec.counts, width=widths, color=ACCENT)
    ax.set_xlabel(spec.x_label, color=SOFT, fontsize=9)
    ax.set_ylabel("rows", color=SOFT, fontsize=9)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(FuncFormatter(_compact))


def _draw_box(ax: Axes, spec: BoxChart) -> None:
    stats = [
        {"whislo": lo, "q1": q1, "med": med, "q3": q3, "whishi": hi, "fliers": []}
        for lo, q1, med, q3, hi in spec.summaries
    ]
    artists = ax.bxp(stats, showfliers=False, patch_artist=True)
    for patch in artists["boxes"]:
        patch.set_facecolor(PRIMARY)
        patch.set_alpha(0.65)
    for line in artists["medians"]:
        line.set_color(INK)
    ax.set_xticklabels(spec.groups, fontsize=8)
    ax.set_ylabel(spec.y_label, color=SOFT, fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(_compact))
