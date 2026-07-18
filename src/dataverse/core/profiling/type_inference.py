"""Semantic column-type inference.

Distinguishes what a column *is* from what pandas parsed it as: text-formatted
numbers/dates/booleans are detected (with a parse-success ratio) so cleaning
can later coerce them, and ID-like columns are separated from real metrics so
dashboards never plot averages of customer IDs.
"""

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Minimum fraction of non-null values that must convert for a type suggestion.
CONVERSION_THRESHOLD = 0.80

_BOOL_TOKENS = {
    "true": True, "false": False, "yes": True, "no": False,
    "y": True, "n": False, "t": True, "f": False, "1": True, "0": False,
}  # fmt: skip

_ID_NAME_RE = re.compile(r"(^id$|_id$|^id_|_id_|_key$|_code$|^sku$|_sku$|number$|_no$)", re.I)

_CURRENCY_RE = re.compile(r"[$€£₹¥,\s]")
_PCT_RE = re.compile(r"%$")


@dataclass(frozen=True)
class TypeInference:
    semantic_type: str
    coerced: pd.Series | None  # converted values (for stats), None if none needed
    suggested_type: str | None  # set when stored dtype ≠ real type (cleaning hint)
    parse_success_pct: float | None


def clean_numeric_strings(s: pd.Series) -> pd.Series:
    """'$1,234.56' → '1234.56', '15%' → '15'. Leaves everything else alone."""
    stripped = s.astype("string").str.strip()
    stripped = stripped.str.replace(_CURRENCY_RE, "", regex=True)
    return stripped.str.replace(_PCT_RE, "", regex=True)


def _try_numeric(nonnull: pd.Series) -> tuple[pd.Series, float]:
    converted = pd.to_numeric(clean_numeric_strings(nonnull), errors="coerce")
    ratio = float(converted.notna().mean()) if len(nonnull) else 0.0
    return converted, ratio


def _try_datetime(nonnull: pd.Series) -> tuple[pd.Series, float]:
    text = nonnull.astype("string").str.strip()
    # Reject pure numbers (they're numeric or Excel serials, handled elsewhere)
    if _try_numeric(nonnull)[1] > 0.95:
        return pd.Series(dtype="datetime64[ns]"), 0.0
    converted = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=False)
    ratio = float(converted.notna().mean()) if len(nonnull) else 0.0
    return converted, ratio


def _try_boolean(nonnull: pd.Series) -> tuple[pd.Series | None, float]:
    text = nonnull.astype("string").str.strip().str.lower()
    distinct = set(text.dropna().unique())
    if not distinct or not distinct.issubset(_BOOL_TOKENS.keys()) or len(distinct) < 2:
        return None, 0.0
    return text.map(_BOOL_TOKENS), 1.0


def _looks_like_id(s: pd.Series, name: str, is_integer_like: bool) -> bool:
    nonnull = s.dropna()
    if nonnull.empty:
        return False
    unique_ratio = nonnull.nunique() / len(nonnull)
    if _ID_NAME_RE.search(name) and unique_ratio > 0.5:
        return True
    return is_integer_like and unique_ratio > 0.98 and len(nonnull) > 20


def infer_column_type(s: pd.Series, name: str) -> TypeInference:
    nonnull = s.dropna()

    if pd.api.types.is_bool_dtype(s):
        return TypeInference("boolean", None, None, None)

    if pd.api.types.is_datetime64_any_dtype(s):
        return TypeInference("datetime", None, None, None)

    if pd.api.types.is_numeric_dtype(s):
        is_int = pd.api.types.is_integer_dtype(s) or bool(
            nonnull.empty or (np.mod(nonnull.astype(float), 1) == 0).all()
        )
        if _looks_like_id(s, name, is_int):
            return TypeInference("id", None, None, None)
        return TypeInference("numeric", None, None, None)

    # Object / string columns: what is this really?
    if nonnull.empty:
        return TypeInference("text", None, None, None)

    as_bool, bool_ratio = _try_boolean(nonnull)
    if as_bool is not None and bool_ratio >= 0.95:
        return TypeInference("boolean", as_bool, "boolean", round(bool_ratio * 100, 1))

    as_dt, dt_ratio = _try_datetime(nonnull)
    if dt_ratio >= CONVERSION_THRESHOLD:
        return TypeInference("datetime", as_dt, "datetime", round(dt_ratio * 100, 1))

    as_num, num_ratio = _try_numeric(nonnull)
    if num_ratio >= CONVERSION_THRESHOLD:
        if _looks_like_id(as_num, name, True):
            return TypeInference("id", None, None, None)
        return TypeInference("numeric", as_num, "numeric", round(num_ratio * 100, 1))

    unique_count = nonnull.nunique()
    # Name-pattern ID detection tolerates some duplication (e.g. duplicated rows).
    if _looks_like_id(s, name, False):
        return TypeInference("id", None, None, None)

    # Categorical when cardinality is low relative to size (or absolutely low).
    if unique_count <= max(20, int(len(nonnull) * 0.05)):
        return TypeInference("categorical", None, None, None)

    return TypeInference("text", None, None, None)
