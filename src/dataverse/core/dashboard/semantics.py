"""Column-role selection: which columns are metrics, dates, and dimensions."""

import re

import pandas as pd

from dataverse.schemas.profiling import ColumnProfile, DatasetProfile

_METRIC_PRIORITY = [
    r"revenue|sales|income|turnover",
    r"profit|margin|earnings",
    r"amount|total|value|price|cost|spend",
    r"quantity|count|units|orders|volume",
    r"rating|score",
]

_MAX_DIMENSION_CARDINALITY = 30


def rank_metrics(profile: DatasetProfile) -> list[str]:
    """Numeric columns ordered by business relevance (name priority, then variance)."""

    def priority(c: ColumnProfile) -> tuple[int, float]:
        for rank, pattern in enumerate(_METRIC_PRIORITY):
            if re.search(pattern, c.name, re.I):
                return rank, 0.0
        spread = (c.stats.std or 0.0) if c.stats else 0.0
        return len(_METRIC_PRIORITY), -spread

    metrics = [c for c in profile.numeric_columns if not c.is_constant]
    return [c.name for c in sorted(metrics, key=priority)]


def pick_date_column(profile: DatasetProfile, df: pd.DataFrame) -> str | None:
    """Datetime column with the widest usable range (prefers parseable text dates too)."""
    candidates = [c.name for c in profile.datetime_columns]
    best, best_span = None, pd.Timedelta(0)
    for name in candidates:
        if name not in df.columns:
            continue
        s = ensure_datetime(df[name])
        clean = s.dropna()
        if len(clean) < 3:
            continue
        span = clean.max() - clean.min()
        if span > best_span:
            best, best_span = name, span
    return best


def rank_dimensions(profile: DatasetProfile) -> list[str]:
    """Categorical columns usable for grouping, lowest cardinality first."""
    dims = [
        c
        for c in profile.columns
        if c.semantic_type in ("categorical", "boolean")
        and 1 < c.unique_count <= _MAX_DIMENSION_CARDINALITY
    ]
    return [c.name for c in sorted(dims, key=lambda c: c.unique_count)]


def ensure_datetime(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    return pd.to_datetime(s.astype("string").str.strip(), errors="coerce", format="mixed")


def ensure_numeric(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return s
    from dataverse.core.profiling.type_inference import clean_numeric_strings

    return pd.to_numeric(clean_numeric_strings(s), errors="coerce")


def pick_time_frequency(span_days: float) -> tuple[str, str]:
    """(pandas freq, human label) for aggregating a time series of this span."""
    if span_days <= 62:
        return "D", "day"
    if span_days <= 370:
        return "W", "week"
    return "ME", "month"
