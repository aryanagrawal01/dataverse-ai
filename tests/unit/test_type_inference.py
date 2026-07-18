import pandas as pd
import pytest

from dataverse.core.profiling.type_inference import clean_numeric_strings, infer_column_type


def infer(values, name="col"):
    return infer_column_type(pd.Series(values), name)


def test_native_numeric():
    assert infer([1.5, 2.5, 3.0]).semantic_type == "numeric"


def test_native_datetime():
    s = pd.Series(pd.to_datetime(["2026-01-01", "2026-01-02"]))
    assert infer_column_type(s, "d").semantic_type == "datetime"


def test_native_boolean():
    assert infer([True, False, True]).semantic_type == "boolean"


def test_currency_strings_detected_as_numeric():
    result = infer(["$1,234.56", "$45.00", "$2,000.99", "$10.50"])
    assert result.semantic_type == "numeric"
    assert result.suggested_type == "numeric"
    assert result.parse_success_pct == 100.0
    assert result.coerced is not None
    assert result.coerced.iloc[0] == pytest.approx(1234.56)


def test_percent_strings_detected_as_numeric():
    assert infer(["15%", "5%", "0%", "20%"]).semantic_type == "numeric"


def test_text_dates_detected_with_partial_parse():
    result = infer(["2026-01-05", "2026-01-06", "garbage", "2026-01-08", "2026-01-09"])
    assert result.semantic_type == "datetime"
    assert result.suggested_type == "datetime"
    assert result.parse_success_pct == 80.0  # 4 of 5 parse


def test_boolean_text_detected():
    result = infer(["Yes", "No", "Yes", "No", "Yes"])
    assert result.semantic_type == "boolean"
    assert result.suggested_type == "boolean"


def test_id_by_name_pattern():
    assert infer([900001, 900002, 900003, 900004], name="customer_id").semantic_type == "id"


def test_id_by_uniqueness():
    values = list(range(100000, 100060))
    assert infer(values, name="account_number").semantic_type == "id"


def test_regular_int_metric_not_id():
    assert infer([1, 2, 2, 3, 1, 2, 4, 1], name="quantity").semantic_type == "numeric"


def test_categorical_low_cardinality():
    assert infer(["North", "South", "East"] * 20).semantic_type == "categorical"


def test_free_text_high_cardinality():
    values = [f"This is a unique sentence number {i} about things." for i in range(100)]
    assert infer(values, name="comment").semantic_type == "text"


def test_string_ids_all_unique():
    values = [f"ORD-{i}" for i in range(50)]
    assert infer(values, name="order_id").semantic_type == "id"


def test_all_null_column_is_text():
    assert infer([None, None, None]).semantic_type == "text"


def test_clean_numeric_strings():
    s = pd.Series(["$1,234.56", "€999", "15%", " 42 "])
    cleaned = clean_numeric_strings(s)
    assert list(cleaned) == ["1234.56", "999", "15", "42"]


def test_pure_numeric_strings_not_datetime():
    """Numbers like 20260105 must not be treated as dates."""
    result = infer(["20260105", "20260106", "20260107", "20260108"], name="code")
    assert result.semantic_type in ("numeric", "id")
