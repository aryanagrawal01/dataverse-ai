"""Build a DashboardSpec from a DataFrame + its profile (deterministic rules)."""

import numpy as np
import pandas as pd

from dataverse.core.dashboard.semantics import (
    ensure_datetime,
    ensure_numeric,
    pick_date_column,
    pick_time_frequency,
    rank_dimensions,
    rank_metrics,
)
from dataverse.schemas.dashboard import (
    BarChart,
    BoxChart,
    ChartSpec,
    DashboardFilters,
    DashboardSpec,
    DonutChart,
    FilterOptions,
    HeatmapChart,
    HistogramChart,
    KpiSpec,
    LineChart,
    Series,
)
from dataverse.schemas.profiling import DatasetProfile

_MAX_KPIS = 4
_TOP_N = 10
_MAX_DONUT_CATEGORIES = 8


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.2f}M"
    if abs(v) >= 10_000:
        return f"{v / 1_000:,.1f}K"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def build_dashboard(
    df: pd.DataFrame,
    profile: DatasetProfile,
    dataset_kind: str,
    filters: DashboardFilters | None = None,
) -> DashboardSpec:
    date_col = pick_date_column(profile, df)
    metrics = [m for m in rank_metrics(profile) if m in df.columns]
    dimensions = [d for d in rank_dimensions(profile) if d in df.columns]

    filter_options = _filter_options(df, date_col, dimensions)
    df = _apply_filters(df, date_col, filter_options.category_column, filters)

    kpis = _kpis(df, metrics, date_col)
    charts: list[ChartSpec] = []

    charts.extend(_time_series_charts(df, metrics, date_col))
    charts.extend(_dimension_charts(df, metrics, dimensions))
    charts.extend(_distribution_charts(df, metrics, dimensions))

    if profile.correlations:
        pearson = next((m for m in profile.correlations if m.method == "pearson"), None)
        if pearson is not None and len(pearson.columns) >= 2:
            charts.append(HeatmapChart(title="Correlations", matrix=pearson))

    return DashboardSpec(
        kpis=kpis, charts=charts, filter_options=filter_options, dataset_kind=dataset_kind
    )


def _filter_options(df: pd.DataFrame, date_col: str | None, dimensions: list[str]) -> FilterOptions:
    opts = FilterOptions()
    if date_col is not None:
        dates = ensure_datetime(df[date_col]).dropna()
        if not dates.empty:
            opts.date_column = date_col
            opts.date_min = str(dates.min().date())
            opts.date_max = str(dates.max().date())
    if dimensions:
        opts.category_column = dimensions[0]
        values = df[dimensions[0]].dropna().astype(str).value_counts()
        opts.category_values = [str(v) for v in values.index[:30]]
    return opts


def _apply_filters(
    df: pd.DataFrame,
    date_col: str | None,
    category_col: str | None,
    filters: DashboardFilters | None,
) -> pd.DataFrame:
    if filters is None:
        return df
    out = df
    if date_col is not None and (filters.date_from or filters.date_to):
        dates = ensure_datetime(out[date_col])
        if filters.date_from:
            out = out[dates >= pd.Timestamp(filters.date_from)]
            dates = dates.loc[out.index]
        if filters.date_to:
            out = out[dates <= pd.Timestamp(filters.date_to) + pd.Timedelta(days=1)]
    if category_col is not None and filters.categories:
        out = out[out[category_col].astype(str).isin(filters.categories)]
    return out


def _kpis(df: pd.DataFrame, metrics: list[str], date_col: str | None) -> list[KpiSpec]:
    kpis: list[KpiSpec] = [KpiSpec(label="Records", value=f"{len(df):,}")]
    for name in metrics[: _MAX_KPIS - 1]:
        numeric = ensure_numeric(df[name]).dropna()
        if numeric.empty:
            continue
        total = float(numeric.sum())
        kpi = KpiSpec(label=f"Total {name}", value=_fmt(total))
        if date_col is not None:
            delta = _period_over_period(df, name, date_col)
            if delta is not None:
                kpi.delta = f"{delta:+.1f}% vs previous period"
                kpi.delta_positive = delta >= 0
        kpis.append(kpi)
    return kpis


def _period_over_period(df: pd.DataFrame, metric: str, date_col: str) -> float | None:
    dates = ensure_datetime(df[date_col])
    values = ensure_numeric(df[metric])
    frame = pd.DataFrame({"d": dates, "v": values}).dropna()
    if len(frame) < 10:
        return None
    end = frame["d"].max()
    span = (end - frame["d"].min()).days
    window = pd.Timedelta(days=max(7, min(span // 2, 90)))
    current = frame[frame["d"] > end - window]["v"].sum()
    previous = frame[(frame["d"] <= end - window) & (frame["d"] > end - 2 * window)]["v"].sum()
    if previous == 0:
        return None
    return float((current - previous) / abs(previous) * 100)


def _time_series_charts(
    df: pd.DataFrame, metrics: list[str], date_col: str | None
) -> list[ChartSpec]:
    if date_col is None or not metrics:
        return []
    charts: list[ChartSpec] = []
    dates = ensure_datetime(df[date_col])
    span_days = float((dates.max() - dates.min()).days) if dates.notna().any() else 0.0
    freq, freq_label = pick_time_frequency(span_days)
    for name in metrics[:2]:
        values = ensure_numeric(df[name])
        frame = pd.DataFrame({"d": dates, "v": values}).dropna()
        if len(frame) < 3:
            continue
        agg = frame.set_index("d").resample(freq)["v"].sum()
        charts.append(
            LineChart(
                title=f"{name} by {freq_label}",
                y_label=name,
                series=[
                    Series(
                        name=name,
                        x=[str(i.date()) for i in agg.index],
                        y=[round(float(v), 2) for v in agg.to_numpy()],
                    )
                ],
            )
        )
    return charts


def _dimension_charts(
    df: pd.DataFrame, metrics: list[str], dimensions: list[str]
) -> list[ChartSpec]:
    if not metrics:
        return []
    charts: list[ChartSpec] = []
    metric = metrics[0]
    values = ensure_numeric(df[metric])
    for dim in dimensions[:2]:
        grouped = (
            pd.DataFrame({"g": df[dim].astype(str), "v": values})
            .dropna()
            .groupby("g")["v"]
            .sum()
            .sort_values(ascending=False)
        )
        if grouped.empty:
            continue
        top = grouped.head(_TOP_N)
        charts.append(
            BarChart(
                title=f"{metric} by {dim}",
                categories=[str(i) for i in top.index],
                values=[round(float(v), 2) for v in top.to_numpy()],
                value_label=metric,
            )
        )
        if len(grouped) <= _MAX_DONUT_CATEGORIES:
            charts.append(
                DonutChart(
                    title=f"{dim} share of {metric}",
                    labels=[str(i) for i in grouped.index],
                    values=[round(float(v), 2) for v in grouped.to_numpy()],
                )
            )
    return charts


def _distribution_charts(
    df: pd.DataFrame, metrics: list[str], dimensions: list[str]
) -> list[ChartSpec]:
    charts: list[ChartSpec] = []
    for name in metrics[:2]:
        numeric = ensure_numeric(df[name]).dropna()
        if len(numeric) < 10:
            continue
        counts, edges = np.histogram(numeric, bins=min(30, max(8, int(len(numeric) ** 0.5))))
        charts.append(
            HistogramChart(
                title=f"Distribution of {name}",
                bin_edges=[round(float(e), 2) for e in edges],
                counts=[int(c) for c in counts],
                x_label=name,
            )
        )
    if metrics and dimensions:
        metric, dim = metrics[0], dimensions[0]
        values = ensure_numeric(df[metric])
        frame = pd.DataFrame({"g": df[dim].astype(str), "v": values}).dropna()
        groups = frame.groupby("g")["v"]
        if 1 < groups.ngroups <= _MAX_DONUT_CATEGORIES:
            names, summaries = [], []
            for g, s in groups:
                if len(s) < 5:
                    continue
                names.append(str(g))
                summaries.append(
                    [
                        round(float(x), 2)
                        for x in (s.min(), s.quantile(0.25), s.median(), s.quantile(0.75), s.max())
                    ]
                )
            if names:
                charts.append(
                    BoxChart(
                        title=f"{metric} spread by {dim}",
                        groups=names,
                        summaries=summaries,
                        y_label=metric,
                    )
                )
    return charts
