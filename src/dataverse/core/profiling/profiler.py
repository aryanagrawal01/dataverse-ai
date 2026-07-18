"""Dataset profiler: orchestrates typing, stats, outliers, correlations, health."""

from typing import Any

import pandas as pd

from dataverse.core.profiling.correlations import correlation_matrices
from dataverse.core.profiling.health import compute_health
from dataverse.core.profiling.outliers import (
    iqr_outlier_mask,
    multivariate_outlier_count,
    zscore_outlier_mask,
)
from dataverse.core.profiling.type_inference import infer_column_type
from dataverse.schemas.profiling import ColumnProfile, DatasetProfile, NumericStats

_SAMPLE_VALUES = 5


def _numeric_stats(s: pd.Series) -> NumericStats:
    clean = s.dropna()
    if clean.empty:
        return NumericStats()

    def f(v: Any) -> float | None:
        return None if pd.isna(v) else round(float(v), 4)

    return NumericStats(
        mean=f(clean.mean()),
        median=f(clean.median()),
        std=f(clean.std()) if len(clean) > 1 else 0.0,
        min=f(clean.min()),
        max=f(clean.max()),
        q1=f(clean.quantile(0.25)),
        q3=f(clean.quantile(0.75)),
        skew=f(clean.skew()) if len(clean) > 2 else None,
    )


def _profile_column(df: pd.DataFrame, name: str) -> tuple[ColumnProfile, pd.Series | None]:
    s = df[name]
    inference = infer_column_type(s, name)
    nonnull = s.dropna()
    missing = int(s.isna().sum())

    profile = ColumnProfile(
        name=name,
        pandas_dtype=str(s.dtype),
        semantic_type=inference.semantic_type,  # type: ignore[arg-type]
        missing_count=missing,
        missing_pct=round(missing / len(s) * 100, 2) if len(s) else 0.0,
        unique_count=int(nonnull.nunique()),
        sample_values=[str(v) for v in nonnull.unique()[:_SAMPLE_VALUES]],
        suggested_type=inference.suggested_type,  # type: ignore[arg-type]
        parse_success_pct=inference.parse_success_pct,
        is_constant=nonnull.nunique() <= 1 and len(nonnull) > 0,
    )

    # The series to compute numeric/datetime facts on (coerced if text-stored).
    effective = inference.coerced if inference.coerced is not None else s

    if profile.semantic_type == "numeric":
        numeric = pd.to_numeric(effective, errors="coerce")
        profile.stats = _numeric_stats(numeric)
        profile.outlier_count_iqr = int(iqr_outlier_mask(numeric).sum())
        profile.outlier_count_zscore = int(zscore_outlier_mask(numeric).sum())
        return profile, numeric

    if profile.semantic_type == "datetime":
        dt = effective if pd.api.types.is_datetime64_any_dtype(effective) else None
        if dt is not None and not dt.dropna().empty:
            profile.min_date = str(dt.min())
            profile.max_date = str(dt.max())
        return profile, None

    return profile, None


def profile_dataframe(df: pd.DataFrame) -> DatasetProfile:
    columns: list[ColumnProfile] = []
    numeric_series: dict[str, pd.Series] = {}

    for name in df.columns:
        profile, numeric = _profile_column(df, str(name))
        columns.append(profile)
        if numeric is not None:
            numeric_series[str(name)] = numeric

    numeric_df = pd.DataFrame(numeric_series) if numeric_series else pd.DataFrame()
    numeric_cols = list(numeric_series.keys())

    duplicate_rows = int(df.duplicated().sum())

    return DatasetProfile(
        row_count=len(df),
        column_count=len(df.columns),
        memory_bytes=int(df.memory_usage(deep=True).sum()),
        duplicate_row_count=duplicate_rows,
        columns=columns,
        correlations=correlation_matrices(numeric_df, numeric_cols),
        multivariate_outlier_count=multivariate_outlier_count(numeric_df, numeric_cols),
        health=compute_health(len(df), duplicate_rows, columns),
    )
