"""Cleaning rules: each takes a DataFrame, returns (new_df, rows_affected, detail).

Rules are pure functions of (df, params) — no I/O, fully unit-testable.
Execution order is fixed (dedupe → types → impute → outliers → drops) so
rules compose predictably.
"""

from collections.abc import Callable
from typing import Any

import pandas as pd

from dataverse.core.profiling.type_inference import _BOOL_TOKENS, clean_numeric_strings
from dataverse.utils.errors import CleaningError

RuleFn = Callable[[pd.DataFrame, dict[str, Any]], tuple[pd.DataFrame, int, str]]


def deduplicate(df: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.DataFrame, int, str]:
    before = len(df)
    out = df.drop_duplicates().reset_index(drop=True)
    removed = before - len(out)
    return out, removed, f"removed {removed:,} exact duplicate rows"


def coerce_type(df: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.DataFrame, int, str]:
    column, target = params["column"], params["target"]
    if column not in df.columns:
        raise CleaningError(f"column {column!r} not in frame")
    s = df[column]
    out = df.copy()
    if target == "numeric":
        converted = pd.to_numeric(clean_numeric_strings(s), errors="coerce")
    elif target == "datetime":
        converted = pd.to_datetime(s.astype("string").str.strip(), errors="coerce", format="mixed")
    elif target == "boolean":
        converted = s.astype("string").str.strip().str.lower().map(_BOOL_TOKENS)
    else:
        raise CleaningError(f"unknown coercion target {target!r}")
    newly_invalid = int((converted.isna() & s.notna()).sum())
    affected = int(s.notna().sum())
    out[column] = converted
    detail = f"converted `{column}` to {target}"
    if newly_invalid:
        detail += f" ({newly_invalid:,} unparseable values became missing)"
    return out, affected, detail


def impute_missing(df: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.DataFrame, int, str]:
    column, strategy = params["column"], params.get("strategy", "median")
    if column not in df.columns:
        raise CleaningError(f"column {column!r} not in frame")
    s = df[column]
    n_missing = int(s.isna().sum())
    if n_missing == 0:
        return df, 0, f"`{column}` had no missing values"
    out = df.copy()

    if strategy == "drop_rows":
        out = out[s.notna()].reset_index(drop=True)
        return out, n_missing, f"dropped {n_missing:,} rows where `{column}` was missing"

    fill: Any
    if strategy == "median":
        fill = pd.to_numeric(s, errors="coerce").median()
    elif strategy == "mean":
        fill = pd.to_numeric(s, errors="coerce").mean()
    elif strategy == "zero":
        fill = 0
    elif strategy == "mode":
        modes = s.mode(dropna=True)
        fill = modes.iloc[0] if not modes.empty else "Unknown"
    elif strategy == "unknown_label":
        fill = "Unknown"
    else:
        raise CleaningError(f"unknown impute strategy {strategy!r}")

    if pd.isna(fill):
        return df, 0, f"`{column}` has no usable values to impute from"
    out[column] = s.fillna(fill)
    shown = f"{fill:,.2f}" if isinstance(fill, float) else str(fill)
    return (
        out,
        n_missing,
        f"filled {n_missing:,} missing `{column}` values with {strategy} ({shown})",
    )


def handle_outliers(df: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.DataFrame, int, str]:
    from dataverse.core.profiling.outliers import iqr_outlier_mask

    column, strategy = params["column"], params.get("strategy", "keep")
    if column not in df.columns:
        raise CleaningError(f"column {column!r} not in frame")
    if strategy == "keep":
        return df, 0, f"kept outliers in `{column}` unchanged"
    numeric = pd.to_numeric(df[column], errors="coerce")
    mask = iqr_outlier_mask(numeric)
    n = int(mask.sum())
    if n == 0:
        return df, 0, f"`{column}` had no outliers"
    out = df.copy()
    if strategy == "remove_rows":
        out = out[~mask].reset_index(drop=True)
        return out, n, f"removed {n:,} outlier rows from `{column}`"
    if strategy == "cap":
        clean = numeric.dropna()
        low, high = clean.quantile(0.01), clean.quantile(0.99)
        out[column] = numeric.clip(low, high)
        return out, n, f"capped {n:,} outliers in `{column}` to the 1st–99th percentile range"
    raise CleaningError(f"unknown outlier strategy {strategy!r}")


def drop_constant_column(df: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.DataFrame, int, str]:
    column = params["column"]
    if column not in df.columns:
        raise CleaningError(f"column {column!r} not in frame")
    out = df.drop(columns=[column])
    return out, len(df), f"dropped constant column `{column}`"


REGISTRY: dict[str, RuleFn] = {
    "deduplicate": deduplicate,
    "coerce_type": coerce_type,
    "impute_missing": impute_missing,
    "handle_outliers": handle_outliers,
    "drop_constant_column": drop_constant_column,
}

# Fixed execution order regardless of plan order.
EXECUTION_ORDER = [
    "deduplicate",
    "coerce_type",
    "impute_missing",
    "handle_outliers",
    "drop_constant_column",
]
