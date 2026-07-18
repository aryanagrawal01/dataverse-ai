from pathlib import Path

import pandas as pd
import pytest

from dataverse.core.insights import extract_facts, narrate
from dataverse.core.profiling import profile_dataframe
from dataverse.llm.null_provider import NullProvider
from tests.fakes import FakeProvider


@pytest.fixture(scope="module")
def sample_df():
    return pd.read_csv(Path("sample_data/retail_sales_demo.csv"))


@pytest.fixture(scope="module")
def sample_facts(sample_df):
    return extract_facts(sample_df, profile_dataframe(sample_df))


class TestFactExtractor:
    def test_metrics_extracted_with_growth(self, sample_facts):
        assert sample_facts.row_count > 2500
        names = [m.name for m in sample_facts.metrics]
        assert "revenue" in names
        revenue = next(m for m in sample_facts.metrics if m.name == "revenue")
        assert revenue.total > 0
        assert revenue.growth_pct is not None
        assert revenue.best_period is not None

    def test_segments_have_shares_that_make_sense(self, sample_facts):
        assert sample_facts.segments
        for s in sample_facts.segments:
            assert 0 < s.top_share_pct <= 100
            assert s.top_value >= s.bottom_value

    def test_data_notes_capture_quality_issues(self, sample_facts):
        assert any("duplicate" in note for note in sample_facts.data_notes)

    def test_no_date_column_still_works(self):
        df = pd.DataFrame({"amount": [1.5, 2.5, 3.5] * 10, "cat": ["a", "b", "c"] * 10})
        facts = extract_facts(df, profile_dataframe(df))
        assert facts.date_column is None
        assert facts.metrics[0].growth_pct is None


class TestNarrator:
    def test_template_fallback_produces_full_set(self, sample_facts):
        insight_set = narrate(sample_facts, NullProvider())
        assert insight_set.model_used == "template"
        kinds = [i.kind for i in insight_set.items]
        assert kinds[0] == "executive_summary"
        assert "recommendation" in kinds
        assert len(insight_set.items) >= 3

    def test_llm_path_parses_items(self, sample_facts):
        provider = FakeProvider(
            [
                {
                    "items": [
                        {"kind": "executive_summary", "title": "Summary", "content": "All good."},
                        {"kind": "trend", "title": "Up", "content": "Revenue rising."},
                    ]
                }
            ]
        )
        insight_set = narrate(sample_facts, provider)
        assert insight_set.model_used == "fake-model"
        assert len(insight_set.items) == 2
        # LLM was given the facts JSON, not raw data
        assert "FACTS" in provider.prompts[0][1]

    def test_bad_llm_json_falls_back_to_template(self, sample_facts):
        insight_set = narrate(sample_facts, FakeProvider(["not json at all"]))
        assert insight_set.model_used == "template"


class TestInsightService:
    def _project(self):
        from dataverse.services import auth_service, ingestion_service, pipeline_service

        user = auth_service.register("ins@example.com", "password9").user
        data = Path("sample_data/retail_sales_demo.csv").read_bytes()
        project = ingestion_service.create_project_from_upload(user.id, "sales.csv", data)
        pipeline_service.profile_project(user.id, project.id)
        return user, project

    def test_generation_is_cached_per_version(self):
        from dataverse.services import insight_service

        user, project = self._project()
        first = insight_service.generate(user.id, project.id)
        second = insight_service.generate(user.id, project.id)
        assert first.items == second.items
        assert first.model_used == "template"  # no key in tests

    def test_force_regenerates(self):
        from dataverse.services import insight_service

        user, project = self._project()
        insight_service.generate(user.id, project.id)
        regenerated = insight_service.generate(user.id, project.id, force=True)
        assert regenerated.items  # replaced, not duplicated
        cached = insight_service.generate(user.id, project.id)
        assert len(cached.items) == len(regenerated.items)


class TestBudget:
    def test_usage_recorded_and_budget_enforced(self, monkeypatch):
        from dataverse.config import get_settings
        from dataverse.services import auth_service, llm_budget
        from dataverse.utils.errors import BudgetExceededError

        user = auth_service.register("budget@example.com", "password9").user
        from dataverse.repositories.base import session_scope
        from dataverse.repositories.project_repo import ProjectRepository

        with session_scope() as s:
            project_id = ProjectRepository(s).create(user.id, "P", None).id

        provider = FakeProvider(["one", "two"])
        provider.complete("s", "u")
        provider.complete("s", "u")
        llm_budget.record_usage(user.id, project_id, "chat", provider.tracker)
        assert llm_budget.spent_usd(project_id) > 0

        monkeypatch.setenv("LLM_BUDGET_USD_PER_PROJECT", "0.0000001")
        get_settings.cache_clear()
        with pytest.raises(BudgetExceededError):
            llm_budget.check_budget(project_id)
