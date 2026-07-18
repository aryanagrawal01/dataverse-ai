import io
from pathlib import Path

import pandas as pd

from dataverse.core.dashboard import build_dashboard
from dataverse.core.dashboard.semantics import pick_time_frequency, rank_metrics
from dataverse.core.profiling import profile_dataframe
from dataverse.schemas.dashboard import DashboardFilters
from tests.fixtures import torture


def _build(df: pd.DataFrame, filters=None):
    return build_dashboard(df, profile_dataframe(df), "raw", filters)


def _sample_df() -> pd.DataFrame:
    return pd.read_csv(Path("sample_data/retail_sales_demo.csv"))


class TestMetricRanking:
    def test_revenue_ranks_first(self):
        df = _sample_df()
        ranked = rank_metrics(profile_dataframe(df))
        assert ranked[0] == "revenue"

    def test_time_frequency_buckets(self):
        assert pick_time_frequency(30)[0] == "D"
        assert pick_time_frequency(200)[0] == "W"
        assert pick_time_frequency(720)[0] == "ME"


class TestDashboardBuild:
    def test_sample_dataset_gets_full_dashboard(self):
        spec = _build(_sample_df())
        assert len(spec.kpis) >= 3
        kinds = {c.kind for c in spec.charts}
        assert "line" in kinds  # time series
        assert "bar" in kinds  # category breakdown
        assert "histogram" in kinds
        assert "heatmap" in kinds
        assert spec.filter_options.date_column == "order_date"
        assert spec.filter_options.category_column is not None

    def test_kpis_have_period_delta_when_dates_exist(self):
        spec = _build(_sample_df())
        revenue_kpi = next(k for k in spec.kpis if "revenue" in k.label)
        assert revenue_kpi.delta is not None
        assert "previous period" in revenue_kpi.delta

    def test_no_numeric_columns_degrades_gracefully(self):
        df = pd.DataFrame({"name": ["a", "b", "c"], "tag": ["x", "y", "x"]})
        spec = _build(df)
        assert spec.kpis[0].label == "Records"
        assert all(c.kind != "line" for c in spec.charts)

    def test_no_datetime_no_line_chart(self):
        df = pd.read_csv(io.BytesIO(torture.numeric_looking_ids_csv()))
        spec = _build(df)
        assert all(c.kind != "line" for c in spec.charts)

    def test_id_columns_never_become_kpis(self):
        df = pd.read_csv(io.BytesIO(torture.numeric_looking_ids_csv()))
        spec = _build(df)
        assert not any("customer_id" in k.label for k in spec.kpis)

    def test_date_filter_reduces_data(self):
        df = _sample_df()
        full = _build(df)
        filtered = _build(df, DashboardFilters(date_from="2025-01-01", date_to="2025-01-31"))
        records_full = int(full.kpis[0].value.replace(",", ""))
        records_filtered = int(filtered.kpis[0].value.replace(",", ""))
        assert 0 < records_filtered < records_full

    def test_category_filter_applies(self):
        df = _sample_df()
        spec = _build(df)
        one_value = spec.filter_options.category_values[0]
        filtered = _build(df, DashboardFilters(categories=[one_value]))
        records_full = int(spec.kpis[0].value.replace(",", ""))
        records_filtered = int(filtered.kpis[0].value.replace(",", ""))
        assert 0 < records_filtered < records_full

    def test_spec_json_roundtrip(self):
        from dataverse.schemas.dashboard import DashboardSpec

        spec = _build(_sample_df())
        restored = DashboardSpec.model_validate(spec.model_dump(mode="json"))
        assert restored == spec


class TestServiceIntegration:
    def test_dashboard_uses_cleaned_after_cleaning(self):
        from pathlib import Path

        from dataverse.core.cleaning import suggest_cleaning
        from dataverse.schemas.cleaning import CleaningPlan, PlanItem
        from dataverse.services import (
            auth_service,
            dashboard_service,
            ingestion_service,
            pipeline_service,
        )

        user = auth_service.register("dash@example.com", "password9").user
        data = Path("sample_data/retail_sales_demo.csv").read_bytes()
        project = ingestion_service.create_project_from_upload(user.id, "sales.csv", data)
        profile = pipeline_service.profile_project(user.id, project.id)

        spec_raw = dashboard_service.build(user.id, project.id)
        assert spec_raw.dataset_kind == "raw"

        plan = CleaningPlan(
            items=[
                PlanItem(rule=s.rule, column=s.column, params=s.params)
                for s in suggest_cleaning(profile)
                if s.enabled_by_default
            ]
        )
        result = pipeline_service.apply_cleaning(user.id, project.id, plan)
        assert result.comparison.health_after > result.comparison.health_before
        assert result.comparison.duplicate_rows_after == 0

        spec_clean = dashboard_service.build(user.id, project.id)
        assert spec_clean.dataset_kind == "cleaned"
        assert any(c.kind == "line" for c in spec_clean.charts)

        log = pipeline_service.get_cleaning_log(user.id, project.id)
        assert len(log) == len(plan.items)

        csv_bytes = pipeline_service.export_csv(user.id, project.id)
        exported = pd.read_csv(io.BytesIO(csv_bytes))
        assert len(exported) == result.comparison.rows_after
