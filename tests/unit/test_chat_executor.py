"""Every DSL operation, valid and invalid — 100% op coverage per the test plan."""

import pandas as pd
import pytest

from dataverse.core.chat.executor import execute_query_plan
from dataverse.schemas.chat import PlanFilter, PlanMetric, QueryPlan
from dataverse.utils.errors import PlanValidationError


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_date": pd.to_datetime(
                ["2026-01-05", "2026-01-15", "2026-02-05", "2026-02-15", "2026-03-05", "2026-03-15"]
            ),
            "region": ["North", "South", "North", "South", "North", "East"],
            "revenue": [100.0, 200.0, 150.0, 250.0, 300.0, 50.0],
            "quantity": [1, 2, 1, 3, 2, 1],
        }
    )


def test_aggregate_grouped(df):
    plan = QueryPlan(
        operation="aggregate",
        metrics=[PlanMetric(column="revenue", agg="sum")],
        group_by=["region"],
    )
    result = execute_query_plan(df, plan)
    assert result.columns == ["region", "sum_revenue"]
    top = result.rows[0]
    assert top[0] == "North"
    assert top[1] == 550.0


def test_aggregate_overall_mean(df):
    plan = QueryPlan(operation="aggregate", metrics=[PlanMetric(column="revenue", agg="mean")])
    result = execute_query_plan(df, plan)
    assert result.rows[0][0] == pytest.approx(175.0)


def test_aggregate_count_and_nunique(df):
    plan = QueryPlan(
        operation="aggregate",
        metrics=[PlanMetric(column="region", agg="nunique")],
    )
    assert execute_query_plan(df, plan).rows[0][0] == 3


def test_top_n_limit_and_sort(df):
    plan = QueryPlan(
        operation="top_n",
        metrics=[PlanMetric(column="revenue", agg="sum")],
        group_by=["region"],
        limit=2,
    )
    result = execute_query_plan(df, plan)
    assert len(result.rows) == 2
    assert result.rows[0][1] >= result.rows[1][1]


def test_trend_monthly(df):
    plan = QueryPlan(
        operation="trend",
        metrics=[PlanMetric(column="revenue", agg="sum")],
        date_column="order_date",
        frequency="ME",
    )
    result = execute_query_plan(df, plan)
    assert len(result.rows) == 3  # Jan, Feb, Mar
    assert result.rows[0][1] == 300.0  # January total


def test_compare_periods(df):
    plan = QueryPlan(
        operation="compare_periods",
        metrics=[PlanMetric(column="revenue", agg="sum")],
        date_column="order_date",
        period_a=["2026-01-01", "2026-01-31"],
        period_b=["2026-02-01", "2026-02-28"],
    )
    result = execute_query_plan(df, plan)
    assert result.rows[0][1] == 300.0
    assert result.rows[1][1] == 400.0
    assert result.summary["delta_pct"] == pytest.approx(33.33, abs=0.01)


def test_describe_numeric_and_categorical(df):
    plan = QueryPlan(operation="describe", columns=["revenue", "region"])
    result = execute_query_plan(df, plan)
    assert len(result.rows) == 2


def test_correlate(df):
    plan = QueryPlan(operation="correlate", columns=["revenue", "quantity"])
    result = execute_query_plan(df, plan)
    assert -1 <= result.summary["pearson_r"] <= 1


def test_filter_rows_with_filters(df):
    plan = QueryPlan(
        operation="filter_rows",
        filters=[PlanFilter(column="region", op="eq", value="North")],
    )
    result = execute_query_plan(df, plan)
    assert result.summary["matching_rows"] == 3


def test_filter_ops(df):
    cases = [
        (PlanFilter(column="revenue", op="gt", value=200), 2),
        (PlanFilter(column="revenue", op="between", value=[100, 200]), 3),
        (PlanFilter(column="region", op="in", value=["North", "East"]), 4),
        (PlanFilter(column="region", op="contains", value="orth"), 3),
        (PlanFilter(column="order_date", op="gte", value="2026-02-01"), 4),
        (PlanFilter(column="region", op="ne", value="North"), 3),
    ]
    for f, expected in cases:
        plan = QueryPlan(operation="filter_rows", filters=[f])
        assert execute_query_plan(df, plan).summary["matching_rows"] == expected, f


def test_unknown_column_rejected(df):
    plan = QueryPlan(operation="aggregate", metrics=[PlanMetric(column="ghost", agg="sum")])
    with pytest.raises(PlanValidationError, match="unknown columns"):
        execute_query_plan(df, plan)


def test_unknown_filter_column_rejected(df):
    plan = QueryPlan(
        operation="filter_rows",
        filters=[PlanFilter(column="__import__", op="eq", value="x")],
    )
    with pytest.raises(PlanValidationError):
        execute_query_plan(df, plan)


def test_aggregate_without_metrics_rejected(df):
    with pytest.raises(PlanValidationError):
        execute_query_plan(df, QueryPlan(operation="aggregate"))


def test_correlate_needs_two_columns(df):
    with pytest.raises(PlanValidationError):
        execute_query_plan(df, QueryPlan(operation="correlate", columns=["revenue"]))


def test_bad_between_filter_rejected(df):
    plan = QueryPlan(
        operation="filter_rows",
        filters=[PlanFilter(column="revenue", op="between", value=[1])],
    )
    with pytest.raises(PlanValidationError):
        execute_query_plan(df, plan)


def test_result_rows_capped():
    big = pd.DataFrame({"g": [f"cat{i}" for i in range(500)], "v": [float(i) for i in range(500)]})
    plan = QueryPlan(
        operation="aggregate",
        metrics=[PlanMetric(column="v", agg="sum")],
        group_by=["g"],
        limit=100,
    )
    result = execute_query_plan(big, plan)
    assert len(result.rows) <= 100
