"""Outlier detection: univariate (IQR, z-score) and multivariate (IsolationForest)."""

import numpy as np
import pandas as pd

_ISOLATION_SAMPLE_CAP = 10_000


def iqr_outlier_mask(s: pd.Series, k: float = 1.5) -> pd.Series:
    """True where value falls outside [Q1 - k*IQR, Q3 + k*IQR]."""
    clean = s.dropna()
    if len(clean) < 8:
        return pd.Series(False, index=s.index)
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return pd.Series(False, index=s.index)
    return (s < q1 - k * iqr) | (s > q3 + k * iqr)


def zscore_outlier_mask(s: pd.Series, threshold: float = 3.0) -> pd.Series:
    clean = s.dropna()
    if len(clean) < 8 or clean.std() == 0 or np.isnan(clean.std()):
        return pd.Series(False, index=s.index)
    z = (s - clean.mean()) / clean.std()
    return z.abs() > threshold


def multivariate_outlier_count(df: pd.DataFrame, numeric_cols: list[str]) -> int:
    """IsolationForest across numeric columns; 0 when not applicable."""
    if len(numeric_cols) < 2:
        return 0
    matrix = df[numeric_cols].dropna()
    if len(matrix) < 50:
        return 0
    if len(matrix) > _ISOLATION_SAMPLE_CAP:
        matrix = matrix.sample(_ISOLATION_SAMPLE_CAP, random_state=42)
    from sklearn.ensemble import IsolationForest

    labels = IsolationForest(random_state=42, contamination="auto").fit_predict(matrix)
    return int((labels == -1).sum())
