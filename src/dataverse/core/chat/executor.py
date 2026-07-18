"""Whitelisted QueryPlan interpreter.

Every operation maps to explicit pandas calls — no eval, no query strings,
no attribute access derived from user input. Column names are validated
against the frame before anything runs.
"""

from typing import Any

import pandas as pd

from dataverse.core.dashboard.semantics import ensure_datetime, ensure_numeric
from dataverse.schemas.chat import PlanFilter, QueryPlan, QueryResult
from dataverse.utils.errors import PlanValidationError

_MAX_RESULT_ROWS = 100


def execute_query_plan(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    _validate_columns(df, plan)
    filtered = _apply_filters(df, plan.filters)

    if plan.operation in ("aggregate", "top_n"):
        return _aggregate(filtered, plan)
    if plan.operation == "trend":
        return _trend(filtered, plan)
    if plan.operation == "compare_periods":
        return _compare_periods(filtered, plan)
    if plan.operation == "describe":
        return _describe(filtered, plan)
    if plan.operation == "correlate":
        return _correlate(filtered, plan)
    if plan.operation == "filter_rows":
        return _filter_rows(filtered, plan)
    raise PlanValidationError(f"unsupported operation {plan.operation!r}")


def _validate_columns(df: pd.DataFrame, plan: QueryPlan) -> None:
    known = set(df.columns)
    referenced = (
        [m.column for m in plan.metrics]
        + plan.group_by
        + [f.column for f in plan.filters]
        + plan.columns
        + ([plan.date_column] if plan.date_column else [])
    )
    unknown = [c for c in referenced if c not in known]
    if unknown:
        raise PlanValidationError(
            f"plan references unknown columns: {unknown}",
            user_message=(
                "I tried to use a column that doesn't exist in this dataset "
                f"({', '.join(unknown[:3])}). Try rephrasing your question."
            ),
        )


def _apply_filters(df: pd.DataFrame, filters: list[PlanFilter]) -> pd.DataFrame:
    out = df
    for f in filters:
        s = out[f.column]
        if f.op in ("gt", "gte", "lt", "lte", "between") or (
            f.op in ("eq", "ne") and isinstance(f.value, (int | float))
        ):
            s_cmp: pd.Series = _comparable(s, f.value)
        else:
            s_cmp = s.astype("string")
        if f.op == "eq":
            mask = s_cmp == _scalar(s_cmp, f.value)
        elif f.op == "ne":
            mask = s_cmp != _scalar(s_cmp, f.value)
        elif f.op == "gt":
            mask = s_cmp > _scalar(s_cmp, f.value)
        elif f.op == "gte":
            mask = s_cmp >= _scalar(s_cmp, f.value)
        elif f.op == "lt":
            mask = s_cmp < _scalar(s_cmp, f.value)
        elif f.op == "lte":
            mask = s_cmp <= _scalar(s_cmp, f.value)
        elif f.op == "in":
            values = f.value if isinstance(f.value, list) else [f.value]
            mask = s.astype("string").isin([str(v) for v in values])
        elif f.op == "between":
            if not isinstance(f.value, list) or len(f.value) != 2:
                raise PlanValidationError("between filter needs [low, high]")
            lo, hi = (_scalar(s_cmp, v) for v in f.value)
            mask = (s_cmp >= lo) & (s_cmp <= hi)
        elif f.op == "contains":
            mask = s.astype("string").str.contains(str(f.value), case=False, na=False)
        else:  # pragma: no cover — pydantic Literal blocks this
            raise PlanValidationError(f"unknown filter op {f.op!r}")
        out = out[mask.fillna(False)]
    return out


def _comparable(s: pd.Series, value: Any) -> pd.Series:
    """Coerce a column so it can be compared with the filter value."""
    if isinstance(value, str) and not _is_number(value):
        return ensure_datetime(s)
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    return ensure_numeric(s)


def _scalar(s_cmp: pd.Series, value: Any) -> Any:
    if pd.api.types.is_datetime64_any_dtype(s_cmp):
        return pd.Timestamp(value)
    if isinstance(value, str) and _is_number(value):
        return float(value)
    return value


def _is_number(v: str) -> bool:
    try:
        float(v)
    except ValueError:
        return False
    return True


def _result_from_frame(frame: pd.DataFrame, summary: dict[str, Any] | None = None) -> QueryResult:
    frame = frame.head(_MAX_RESULT_ROWS)
    return QueryResult(
        columns=[str(c) for c in frame.columns],
        rows=[[_jsonable(v) for v in row] for row in frame.itertuples(index=False)],
        summary=summary or {},
    )


def _jsonable(v: Any) -> Any:
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return str(v.date())
    if hasattr(v, "item"):  # numpy scalars
        v = v.item()
    if isinstance(v, float):
        return round(v, 4)
    return v


def _named(metric_col: str, agg: str) -> str:
    return f"{agg}_{metric_col}"


def _aggregate(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    if not plan.metrics:
        raise PlanValidationError("aggregate needs at least one metric")
    prepared = df.copy()
    agg_map: dict[str, tuple[str, str]] = {}
    for m in plan.metrics:
        if m.agg in ("count", "nunique"):
            prepared[m.column] = df[m.column]
        else:
            prepared[m.column] = ensure_numeric(df[m.column])
        agg_map[_named(m.column, m.agg)] = (m.column, m.agg)

    if plan.group_by:
        grouped = prepared.groupby([prepared[g].astype(str) for g in plan.group_by]).agg(
            **{name: pd.NamedAgg(column=col, aggfunc=agg) for name, (col, agg) in agg_map.items()}
        )
        grouped = grouped.reset_index()
        sort_col = next(iter(agg_map))
        grouped = grouped.sort_values(sort_col, ascending=not plan.sort_desc).head(plan.limit)
        return _result_from_frame(grouped, {"groups": len(grouped)})

    row = {
        name: prepared[col].nunique()
        if agg == "nunique"
        else (prepared[col].count() if agg == "count" else getattr(prepared[col], agg)())
        for name, (col, agg) in agg_map.items()
    }
    return _result_from_frame(pd.DataFrame([row]))


def _trend(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    if plan.date_column is None or not plan.metrics:
        raise PlanValidationError("trend needs date_column and one metric")
    m = plan.metrics[0]
    dates = ensure_datetime(df[plan.date_column])
    values = ensure_numeric(df[m.column]) if m.agg != "count" else df[m.column]
    frame = pd.DataFrame({"d": dates, "v": values}).dropna(subset=["d"])
    if frame.empty:
        raise PlanValidationError("no usable dates for trend")
    span = float((frame["d"].max() - frame["d"].min()).days)
    freq = plan.frequency or ("D" if span <= 62 else ("W" if span <= 370 else "ME"))
    resampled = frame.set_index("d").resample(freq)["v"]
    series = resampled.count() if m.agg == "count" else getattr(resampled, m.agg)()
    out = pd.DataFrame(
        {
            "period": [str(i.date()) for i in series.index],
            _named(m.column, m.agg): series.to_numpy(),
        }
    )
    return _result_from_frame(out, {"frequency": freq})


def _compare_periods(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    if plan.date_column is None or not plan.metrics or not plan.period_a or not plan.period_b:
        raise PlanValidationError("compare_periods needs date_column, metric, period_a, period_b")
    m = plan.metrics[0]
    dates = ensure_datetime(df[plan.date_column])
    values = ensure_numeric(df[m.column])

    def period_value(period: list[str]) -> float:
        lo, hi = pd.Timestamp(period[0]), pd.Timestamp(period[1]) + pd.Timedelta(days=1)
        mask = (dates >= lo) & (dates < hi)
        subset = values[mask].dropna()
        if m.agg == "count":
            return float(mask.sum())
        return float(getattr(subset, m.agg)()) if not subset.empty else 0.0

    a, b = period_value(plan.period_a), period_value(plan.period_b)
    delta_pct = round((b - a) / abs(a) * 100, 2) if a else None
    out = pd.DataFrame(
        {
            "period": [
                f"{plan.period_a[0]} → {plan.period_a[1]}",
                f"{plan.period_b[0]} → {plan.period_b[1]}",
            ],
            _named(m.column, m.agg): [round(a, 2), round(b, 2)],
        }
    )
    return _result_from_frame(out, {"delta_pct": delta_pct})


def _describe(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    targets = plan.columns or [m.column for m in plan.metrics]
    if not targets:
        raise PlanValidationError("describe needs target columns")
    rows = []
    for col in targets:
        numeric = ensure_numeric(df[col]).dropna()
        if numeric.empty:
            s = df[col]
            rows.append(
                {
                    "column": col,
                    "count": int(s.notna().sum()),
                    "unique": int(s.nunique()),
                    "top": str(s.mode(dropna=True).iloc[0]) if s.notna().any() else None,
                }
            )
        else:
            rows.append(
                {
                    "column": col,
                    "count": int(numeric.count()),
                    "mean": round(float(numeric.mean()), 4),
                    "median": round(float(numeric.median()), 4),
                    "min": round(float(numeric.min()), 4),
                    "max": round(float(numeric.max()), 4),
                }
            )
    return _result_from_frame(pd.DataFrame(rows))


def _correlate(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    if len(plan.columns) != 2:
        raise PlanValidationError("correlate needs exactly two columns")
    a = ensure_numeric(df[plan.columns[0]])
    b = ensure_numeric(df[plan.columns[1]])
    frame = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(frame) < 3:
        raise PlanValidationError("not enough overlapping numeric data to correlate")
    r = round(float(frame["a"].corr(frame["b"])), 4)
    out = pd.DataFrame([{"column_a": plan.columns[0], "column_b": plan.columns[1], "pearson_r": r}])
    return _result_from_frame(out, {"pearson_r": r, "n": len(frame)})


def _filter_rows(df: pd.DataFrame, plan: QueryPlan) -> QueryResult:
    subset = df.head(min(plan.limit, 20))
    return _result_from_frame(subset, {"matching_rows": len(df)})
