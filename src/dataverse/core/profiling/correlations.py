"""Correlation matrices for numeric columns."""

import pandas as pd

from dataverse.schemas.profiling import CorrelationMatrix

_MAX_COLUMNS = 15


def correlation_matrices(df: pd.DataFrame, numeric_cols: list[str]) -> list[CorrelationMatrix]:
    cols = numeric_cols[:_MAX_COLUMNS]
    if len(cols) < 2:
        return []
    sub = df[cols]
    result = []
    for method in ("pearson", "spearman"):
        matrix = sub.corr(method=method, numeric_only=True).round(3)
        values: list[list[float | None]] = [
            [None if pd.isna(v) else float(v) for v in row] for row in matrix.to_numpy()
        ]
        result.append(CorrelationMatrix(method=method, columns=cols, values=values))
    return result
