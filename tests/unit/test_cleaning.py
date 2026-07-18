import io

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as hst

from dataverse.core.cleaning import execute_plan, suggest_cleaning
from dataverse.core.cleaning import rules as cleaning_rules
from dataverse.core.profiling import profile_dataframe
from dataverse.schemas.cleaning import CleaningPlan, PlanItem
from dataverse.utils.errors import CleaningError
from tests.fixtures import torture


def _df(data: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data))


class TestRules:
    def test_deduplicate(self):
        df = _df(torture.all_duplicates_csv())
        out, affected, _ = cleaning_rules.deduplicate(df, {})
        assert len(out) == 1
        assert affected == 19

    def test_coerce_numeric_currency(self):
        df = _df(torture.currency_csv())
        out, affected, detail = cleaning_rules.coerce_type(df, {"column": "price_usd", "target": "numeric"})
        assert out["price_usd"].dtype.kind == "f"
        assert out["price_usd"].iloc[0] == pytest.approx(1234.56)
        assert affected == 5

    def test_coerce_datetime_counts_invalid(self):
        df = _df(torture.mixed_date_formats_csv())
        out, _, detail = cleaning_rules.coerce_type(df, {"column": "iso_date", "target": "datetime"})
        assert str(out["iso_date"].dtype).startswith("datetime64")

    def test_coerce_unknown_column_raises(self):
        with pytest.raises(CleaningError):
            cleaning_rules.coerce_type(_df(torture.clean_sales_csv()), {"column": "ghost", "target": "numeric"})

    def test_impute_median(self):
        df = pd.DataFrame({"v": [1.0, 2.0, None, 100.0, None]})
        out, affected, _ = cleaning_rules.impute_missing(df, {"column": "v", "strategy": "median"})
        assert affected == 2
        assert out["v"].isna().sum() == 0
        assert out["v"].iloc[2] == 2.0  # median of 1,2,100

    def test_impute_unknown_label(self):
        df = pd.DataFrame({"c": ["a", None, "b", None]})
        out, affected, _ = cleaning_rules.impute_missing(df, {"column": "c", "strategy": "unknown_label"})
        assert affected == 2
        assert list(out["c"]) == ["a", "Unknown", "b", "Unknown"]

    def test_impute_drop_rows(self):
        df = pd.DataFrame({"v": [1.0, None, 3.0], "o": [1, 2, 3]})
        out, affected, _ = cleaning_rules.impute_missing(df, {"column": "v", "strategy": "drop_rows"})
        assert len(out) == 2
        assert affected == 1

    def test_impute_all_missing_column_is_noop(self):
        df = pd.DataFrame({"v": [None, None, None]})
        out, affected, _ = cleaning_rules.impute_missing(df, {"column": "v", "strategy": "median"})
        assert affected == 0

    def test_outlier_cap(self):
        df = _df(torture.outlier_csv())
        out, affected, _ = cleaning_rules.handle_outliers(df, {"column": "value", "strategy": "cap"})
        assert affected >= 2
        assert out["value"].max() < 5000
        assert len(out) == len(df)  # capping never drops rows

    def test_outlier_remove(self):
        df = _df(torture.outlier_csv())
        out, affected, _ = cleaning_rules.handle_outliers(df, {"column": "value", "strategy": "remove_rows"})
        assert len(out) == len(df) - affected
        assert out["value"].max() < 5000

    def test_outlier_keep_is_noop(self):
        df = _df(torture.outlier_csv())
        out, affected, _ = cleaning_rules.handle_outliers(df, {"column": "value", "strategy": "keep"})
        assert out.equals(df)
        assert affected == 0

    def test_drop_constant_column(self):
        df = _df(torture.constant_column_csv())
        out, _, _ = cleaning_rules.drop_constant_column(df, {"column": "country"})
        assert "country" not in out.columns


class TestSuggester:
    def test_suggestions_cover_sample_dataset_issues(self):
        from pathlib import Path

        df = pd.read_csv(Path("sample_data/retail_sales_demo.csv"))
        profile = profile_dataframe(df)
        suggestions = suggest_cleaning(profile)
        rules = {s.rule for s in suggestions}
        assert "deduplicate" in rules
        assert "coerce_type" in rules
        assert "impute_missing" in rules
        by_id = {s.id for s in suggestions}
        assert "coerce_type:order_date" in by_id
        assert "coerce_type:unit_price" in by_id

    def test_outlier_suggestions_disabled_by_default(self):
        profile = profile_dataframe(_df(torture.outlier_csv()))
        suggestions = suggest_cleaning(profile)
        outlier_sugs = [s for s in suggestions if s.rule == "handle_outliers"]
        assert outlier_sugs
        assert all(not s.enabled_by_default for s in outlier_sugs)

    def test_clean_data_yields_no_suggestions(self):
        profile = profile_dataframe(
            pd.DataFrame({"a": [1.5, 2.5, 3.5, 4.5], "b": ["x", "y", "x", "y"]})
        )
        assert suggest_cleaning(profile) == []


class TestExecutor:
    def test_full_plan_on_sample_dataset(self):
        from pathlib import Path

        df = pd.read_csv(Path("sample_data/retail_sales_demo.csv"))
        profile = profile_dataframe(df)
        plan = CleaningPlan(
            items=[
                PlanItem(rule=s.rule, column=s.column, params=s.params)
                for s in suggest_cleaning(profile)
                if s.enabled_by_default
            ]
        )
        cleaned, log = execute_plan(df, plan)

        after = profile_dataframe(cleaned)
        assert after.duplicate_row_count == 0
        assert after.column("order_date").semantic_type == "datetime"
        assert after.column("unit_price").semantic_type == "numeric"
        assert after.column("unit_price").suggested_type is None
        assert after.health.score > profile.health.score
        assert len(log) == len(plan.items)

    def test_execution_order_is_fixed(self):
        """Impute must run after coercion even if listed first in the plan."""
        df = pd.DataFrame({"price": ["$10", None, "$30", "$20"]})
        plan = CleaningPlan(
            items=[
                PlanItem(rule="impute_missing", column="price", params={"strategy": "median"}),
                PlanItem(rule="coerce_type", column="price", params={"target": "numeric"}),
            ]
        )
        cleaned, log = execute_plan(df, plan)
        assert log[0].rule == "coerce_type"
        assert cleaned["price"].isna().sum() == 0
        assert cleaned["price"].iloc[1] == 20.0  # median of 10, 30, 20

    def test_plan_removing_all_rows_rejected(self):
        df = pd.DataFrame({"v": [None, None, None], "w": [1, 2, 3]})
        plan = CleaningPlan(
            items=[PlanItem(rule="impute_missing", column="v", params={"strategy": "drop_rows"})]
        )
        with pytest.raises(CleaningError):
            execute_plan(df, plan)

    def test_unknown_rule_rejected(self):
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CleaningPlan(items=[PlanItem(rule="rm_rf", params={})])  # type: ignore[arg-type]


@settings(max_examples=25, deadline=None)
@given(
    values=hst.lists(
        hst.one_of(hst.floats(allow_nan=False, allow_infinity=False, width=32), hst.none()),
        min_size=1,
        max_size=50,
    )
)
def test_impute_median_never_leaves_missing_when_any_value_exists(values):
    """Property: after median imputation, a numeric column has no NaNs
    (unless it was entirely empty)."""
    df = pd.DataFrame({"v": pd.Series(values, dtype="float64")})
    out, _, _ = cleaning_rules.impute_missing(df, {"column": "v", "strategy": "median"})
    if df["v"].notna().any():
        assert out["v"].isna().sum() == 0
    else:
        assert out["v"].isna().all()
