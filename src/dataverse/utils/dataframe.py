"""DataFrame ⇄ Parquet serialization and display guardrails."""

import io

import pandas as pd


def to_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Serialize for storage. Object columns are stringified first so any
    parsed frame (mixed types included) survives the Parquet roundtrip."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].astype("string")
    buf = io.BytesIO()
    out.to_parquet(buf, engine="pyarrow", index=False)
    return buf.getvalue()


def from_parquet_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(data), engine="pyarrow")  # type: ignore[call-overload]


def sample_for_display(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df
    return df.head(max_rows)


def dedupe_column_names(columns: list[str]) -> list[str]:
    """Make duplicate/blank column names unique and non-empty."""
    seen: dict[str, int] = {}
    result = []
    for i, raw in enumerate(columns):
        name = str(raw).strip() or f"column_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        result.append(name)
    return result
