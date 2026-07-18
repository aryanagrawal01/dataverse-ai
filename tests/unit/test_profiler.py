import io

import pandas as pd

from dataverse.core.profiling import profile_dataframe
from tests.fixtures import torture


def _profile_csv(data: bytes):
    return profile_dataframe(pd.read_csv(io.BytesIO(data)))


def test_clean_dataset_gets_high_health():
    profile = _profile_csv(torture.clean_sales_csv())
    assert profile.row_count == 10
    assert profile.health.score >= 90
    assert profile.duplicate_row_count == 0


def test_missing_values_reported_and_penalized():
    profile = _profile_csv(torture.missing_heavy_csv())
    col = profile.column("mostly_missing")
    assert col.missing_pct == 95.0
    kinds = {i.kind for i in profile.health.issues}
    assert "missing_values" in kinds
    assert profile.health.score < 80


def test_duplicates_detected():
    profile = _profile_csv(torture.all_duplicates_csv())
    assert profile.duplicate_row_count == 19
    assert any(i.kind == "duplicate_rows" for i in profile.health.issues)


def test_constant_column_flagged():
    profile = _profile_csv(torture.constant_column_csv())
    assert profile.column("country").is_constant
    assert any(i.kind == "constant_column" for i in profile.health.issues)


def test_outliers_counted():
    profile = _profile_csv(torture.outlier_csv())
    col = profile.column("value")
    assert col.outlier_count_iqr >= 2
    assert col.outlier_count_zscore >= 2


def test_id_columns_get_no_stats():
    profile = _profile_csv(torture.numeric_looking_ids_csv())
    id_col = profile.column("customer_id")
    assert id_col.semantic_type == "id"
    assert id_col.stats is None
    rev = profile.column("revenue")
    assert rev.semantic_type == "numeric"
    assert rev.stats is not None


def test_correlations_present_for_multi_numeric():
    # Floats, not unique ints: perfectly-unique integer sequences are
    # (correctly) classified as IDs and excluded from correlation.
    df = pd.DataFrame(
        {"a": [x * 1.5 for x in range(50)], "b": [x * 2.5 + 1 for x in range(50)], "c": [7] * 50}
    )
    profile = profile_dataframe(df)
    assert len(profile.correlations) == 2  # pearson + spearman
    pearson = profile.correlations[0]
    ia, ib = pearson.columns.index("a"), pearson.columns.index("b")
    assert pearson.values[ia][ib] == 1.0


def test_datetime_min_max_recorded():
    df = pd.read_csv(io.BytesIO(torture.clean_sales_csv()))
    profile = profile_dataframe(df)
    col = profile.column("order_date")
    assert col.semantic_type == "datetime"
    assert col.min_date is not None and col.min_date.startswith("2026-01-05")


def test_profile_roundtrips_through_json():
    """profile_json storage: dump → load must be lossless."""
    from dataverse.schemas.profiling import DatasetProfile

    profile = _profile_csv(torture.currency_csv())
    dumped = profile.model_dump(mode="json")
    restored = DatasetProfile.model_validate(dumped)
    assert restored == profile
