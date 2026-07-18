"""Performance guardrails (marked slow; excluded from PR CI)."""

import time

import numpy as np
import pandas as pd
import pytest


@pytest.mark.slow
def test_profile_200k_rows_under_30s():
    from dataverse.core.profiling import profile_dataframe

    rng = np.random.default_rng(1)
    n = 200_000
    df = pd.DataFrame(
        {
            "order_id": [f"ORD-{i}" for i in range(n)],
            "order_date": pd.date_range("2024-01-01", periods=n, freq="min").astype(str),
            "region": rng.choice(["North", "South", "East", "West"], n),
            "revenue": rng.gamma(2.0, 150.0, n).round(2),
            "quantity": rng.integers(1, 10, n),
        }
    )
    started = time.monotonic()
    profile = profile_dataframe(df)
    elapsed = time.monotonic() - started
    assert profile.row_count == n
    assert elapsed < 30, f"profiling took {elapsed:.1f}s"


@pytest.mark.slow
def test_parquet_roundtrip_200k_rows():
    from dataverse.utils.dataframe import from_parquet_bytes, to_parquet_bytes

    n = 200_000
    df = pd.DataFrame({"a": range(n), "b": [f"text {i}" for i in range(n)]})
    data = to_parquet_bytes(df)
    restored = from_parquet_bytes(data)
    assert len(restored) == n
