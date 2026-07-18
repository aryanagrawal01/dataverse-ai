"""Full UI journey: register → sample project → all workspace tabs render →
chat starter question degrades gracefully without an API key.

Regression coverage for the M6 avatar crash: every project tab body executes
in this test, so any Streamlit API misuse in a tab fails here.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def _signed_in_with_sample() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=120)
    at.run()
    at.text_input(key="reg_name").input("Journey Tester")
    at.text_input(key="reg_email").input("journey@example.com")
    at.text_input(key="reg_pw").input("password9")
    at.button(key="FormSubmitter:register_form-Create account").set_value(True).run()

    # Projects empty state → upload page → sample dataset
    new_project = next(b for b in at.button if "New project" in str(b.label))
    new_project.click().run()
    sample = next(b for b in at.button if "sample dataset" in str(b.label))
    sample.click().run()
    assert not at.exception, f"sample ingestion crashed: {at.exception}"
    return at


def test_project_workspace_renders_every_tab():
    at = _signed_in_with_sample()
    rendered = " ".join(md.value for md in at.markdown)
    # Data Health + cleaning suggestions
    assert "Suggested fixes" in rendered or "Issues found" in rendered
    # Insights cards rendered (template mode)
    assert "Executive summary" in rendered
    # Chat starter suggestions present
    assert any("revenue" in str(b.label) for b in at.button)
    assert not at.exception


def test_chat_without_api_key_shows_friendly_warning_not_crash():
    at = _signed_in_with_sample()
    starter = next(b for b in at.button if "highest total revenue" in str(b.label))
    starter.click().run()
    assert not at.exception, f"chat crashed: {at.exception}"
    warnings = " ".join(str(w.value) for w in at.warning)
    assert "OPENAI_API_KEY" in warnings
    # No generic error banner
    errors = " ".join(str(e.value) for e in at.error)
    assert "Something went wrong" not in errors
