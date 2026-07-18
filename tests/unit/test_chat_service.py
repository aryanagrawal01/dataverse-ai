from pathlib import Path

import pytest

from dataverse.core.chat import compose_answer, plan_query, starter_questions
from dataverse.core.chat.executor import execute_query_plan
from dataverse.schemas.chat import PlanMetric, QueryPlan
from dataverse.utils.errors import LLMUnavailableError, PlanValidationError
from tests.fakes import FakeProvider


def _profile():
    import pandas as pd

    from dataverse.core.profiling import profile_dataframe

    return profile_dataframe(pd.read_csv(Path("sample_data/retail_sales_demo.csv")))


class TestPlanner:
    def test_valid_plan_parsed(self):
        provider = FakeProvider(
            [
                {
                    "operation": "aggregate",
                    "metrics": [{"column": "revenue", "agg": "sum"}],
                    "group_by": ["region"],
                    "chart_hint": "bar",
                }
            ]
        )
        plan = plan_query("Which region made the most revenue?", _profile(), provider)
        assert plan.operation == "aggregate"
        assert plan.group_by == ["region"]
        # Prompt contains schema but no raw rows
        system, user = provider.prompts[0]
        assert "SCHEMA" in user
        assert "ORD-" not in user or user.count("ORD-") <= 3  # sample values only

    def test_invalid_then_corrected_plan_retries_once(self):
        provider = FakeProvider(
            [
                {"operation": "launch_missiles"},
                {
                    "operation": "describe",
                    "columns": ["revenue"],
                },
            ]
        )
        plan = plan_query("Describe revenue", _profile(), provider)
        assert plan.operation == "describe"
        assert len(provider.prompts) == 2

    def test_model_declining_raises_unanswerable(self):
        provider = FakeProvider([{"error": "The dataset has no employee salary data."}])
        with pytest.raises(PlanValidationError, match="salary"):
            plan_query("What is the average salary?", _profile(), provider)

    def test_two_bad_responses_give_up(self):
        provider = FakeProvider(["garbage", "more garbage"])
        with pytest.raises(PlanValidationError):
            plan_query("anything", _profile(), provider)

    def test_starter_questions_derived_from_schema(self):
        questions = starter_questions(_profile())
        assert questions
        assert any("revenue" in q for q in questions)


class TestComposer:
    def _result(self):
        import pandas as pd

        df = pd.DataFrame({"region": ["N", "S"], "revenue": [100.0, 50.0]})
        plan = QueryPlan(
            operation="aggregate",
            metrics=[PlanMetric(column="revenue", agg="sum")],
            group_by=["region"],
            chart_hint="bar",
        )
        return plan, execute_query_plan(df, plan)

    def test_llm_answer_with_chart(self):
        plan, result = self._result()
        provider = FakeProvider(["North leads with 100.00 in revenue."])
        answer = compose_answer("Which region leads?", plan, result, provider)
        assert "North leads" in answer.text
        assert answer.chart is not None and answer.chart.kind == "bar"
        # LLM saw the computed result verbatim
        assert "100.0" in provider.prompts[0][1]

    def test_template_answer_without_llm(self):
        from dataverse.llm.null_provider import NullProvider

        plan, result = self._result()
        answer = compose_answer("Which region leads?", plan, result, NullProvider())
        assert answer.model_used == "template"
        assert answer.text


class TestChatService:
    def _project(self):
        from dataverse.services import auth_service, ingestion_service, pipeline_service

        user = auth_service.register("chat@example.com", "password9").user
        data = Path("sample_data/retail_sales_demo.csv").read_bytes()
        project = ingestion_service.create_project_from_upload(user.id, "sales.csv", data)
        pipeline_service.profile_project(user.id, project.id)
        return user, project

    def test_ask_requires_llm(self):
        from dataverse.services import chat_service

        user, project = self._project()
        with pytest.raises(LLMUnavailableError):
            chat_service.ask(user.id, project.id, "Which region leads?")

    def test_full_ask_flow_with_fake_provider(self, monkeypatch):
        from dataverse.services import chat_service

        user, project = self._project()
        fake = FakeProvider(
            [
                {
                    "operation": "aggregate",
                    "metrics": [{"column": "revenue", "agg": "sum"}],
                    "group_by": ["region"],
                    "chart_hint": "bar",
                },
                "West leads on revenue.",
            ]
        )
        monkeypatch.setattr(chat_service, "make_provider", lambda: fake)

        answer = chat_service.ask(user.id, project.id, "Which region has the most revenue?")
        assert answer.plan is not None and answer.plan.operation == "aggregate"
        assert answer.chart is not None
        assert answer.result is not None and answer.result.rows

        # History persisted with audit trail
        messages = chat_service.history(user.id, project.id)
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[1].plan is not None
        assert messages[1].chart is not None

        # Usage recorded against the project
        from dataverse.services import llm_budget

        assert llm_budget.spent_usd(project.id) > 0

    def test_unanswerable_question_persists_friendly_reply(self, monkeypatch):
        from dataverse.services import chat_service
        from dataverse.utils.errors import ChatError

        user, project = self._project()
        fake = FakeProvider([{"error": "No employee data in this dataset."}])
        monkeypatch.setattr(chat_service, "make_provider", lambda: fake)

        with pytest.raises(ChatError):
            chat_service.ask(user.id, project.id, "Who is the best employee?")
        messages = chat_service.history(user.id, project.id)
        assert messages[-1].role == "assistant"
        assert "employee" in messages[-1].content

    def test_question_length_validated(self):
        from dataverse.services import chat_service
        from dataverse.utils.errors import ValidationError

        user, project = self._project()
        with pytest.raises(ValidationError):
            chat_service.ask(user.id, project.id, "x" * 600)
