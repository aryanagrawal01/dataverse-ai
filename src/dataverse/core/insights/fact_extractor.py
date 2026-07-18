"""Deterministic fact extraction — the ONLY source of numbers for AI insights."""

import pandas as pd

from dataverse.core.dashboard.semantics import (
    ensure_datetime,
    ensure_numeric,
    pick_date_column,
    pick_time_frequency,
    rank_dimensions,
    rank_metrics,
)
from dataverse.schemas.insights import AnomalyFacts, FactPack, MetricFacts, SegmentFacts
from dataverse.schemas.profiling import DatasetProfile

_MAX_METRICS = 3
_MAX_SEGMENTS = 3


def extract_facts(df: pd.DataFrame, profile: DatasetProfile) -> FactPack:
    date_col = pick_date_column(profile, df)
    metrics = [m for m in rank_metrics(profile) if m in df.columns][:_MAX_METRICS]
    dimensions = [d for d in rank_dimensions(profile) if d in df.columns][:_MAX_SEGMENTS]

    pack = FactPack(
        row_count=profile.row_count,
        column_count=profile.column_count,
        date_column=date_col,
        health_score=profile.health.score,
    )

    dates = ensure_datetime(df[date_col]) if date_col else None
    if dates is not None and dates.notna().any():
        pack.date_from = str(dates.min().date())
        pack.date_to = str(dates.max().date())

    for name in metrics:
        pack.metrics.append(_metric_facts(df, name, dates))

    primary = metrics[0] if metrics else None
    if primary is not None:
        for dim in dimensions:
            facts = _segment_facts(df, dim, primary)
            if facts is not None:
                pack.segments.append(facts)

    for c in profile.columns:
        if c.semantic_type == "numeric" and c.outlier_count_iqr > 0 and c.name in df.columns:
            numeric = ensure_numeric(df[c.name]).dropna()
            pack.anomalies.append(
                AnomalyFacts(
                    column=c.name,
                    outlier_count=c.outlier_count_iqr,
                    outlier_pct=round(c.outlier_count_iqr / max(profile.row_count, 1) * 100, 2),
                    example_high=round(float(numeric.max()), 2) if not numeric.empty else None,
                    example_low=round(float(numeric.min()), 2) if not numeric.empty else None,
                )
            )

    for c in profile.columns:
        if c.missing_pct > 5:
            pack.data_notes.append(f"{c.name} is missing {c.missing_pct:.1f}% of values")
    if profile.duplicate_row_count > 0:
        pack.data_notes.append(f"{profile.duplicate_row_count:,} duplicate rows present")

    return pack


def _metric_facts(df: pd.DataFrame, name: str, dates: pd.Series | None) -> MetricFacts:
    numeric = ensure_numeric(df[name])
    clean = numeric.dropna()
    facts = MetricFacts(
        name=name,
        total=round(float(clean.sum()), 2),
        mean=round(float(clean.mean()), 2) if not clean.empty else 0.0,
    )
    if dates is None or not dates.notna().any():
        return facts

    frame = pd.DataFrame({"d": dates, "v": numeric}).dropna()
    if len(frame) < 10:
        return facts

    span_days = float((frame["d"].max() - frame["d"].min()).days)
    freq, _ = pick_time_frequency(span_days)
    series = frame.set_index("d").resample(freq)["v"].sum()
    if len(series) >= 4:
        half = len(series) // 2
        first, second = float(series.iloc[:half].sum()), float(series.iloc[half:].sum())
        if first != 0:
            facts.growth_pct = round((second - first) / abs(first) * 100, 1)
        best_idx, worst_idx = pd.Timestamp(series.idxmax()), pd.Timestamp(series.idxmin())
        facts.best_period = str(best_idx.date())
        facts.best_period_value = round(float(series.max()), 2)
        facts.worst_period = str(worst_idx.date())
        facts.worst_period_value = round(float(series.min()), 2)
    return facts


def _segment_facts(df: pd.DataFrame, dimension: str, metric: str) -> SegmentFacts | None:
    values = ensure_numeric(df[metric])
    grouped = (
        pd.DataFrame({"g": df[dimension].astype(str), "v": values})
        .dropna()
        .groupby("g")["v"]
        .sum()
        .sort_values(ascending=False)
    )
    if len(grouped) < 2:
        return None
    total = float(grouped.sum())
    return SegmentFacts(
        dimension=dimension,
        metric=metric,
        top_name=str(grouped.index[0]),
        top_value=round(float(grouped.iloc[0]), 2),
        top_share_pct=round(float(grouped.iloc[0]) / total * 100, 1) if total else 0.0,
        bottom_name=str(grouped.index[-1]),
        bottom_value=round(float(grouped.iloc[-1]), 2),
        segments_count=len(grouped),
    )
