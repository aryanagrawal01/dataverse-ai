"""UI-level auth flow: register through the real form, land on projects."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def _boot() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    return at


def test_unauthenticated_user_sees_auth_page():
    at = _boot()
    assert not at.exception
    rendered = " ".join(md.value for md in at.markdown)
    assert "Welcome to DataVerse AI" in rendered


def test_register_flow_lands_on_projects_empty_state():
    at = _boot()
    at.text_input(key="reg_name").input("Flow Tester")
    at.text_input(key="reg_email").input("flow@example.com")
    at.text_input(key="reg_pw").input("password9")
    at.button(key="FormSubmitter:register_form-Create account").set_value(True).run()

    assert not at.exception
    rendered = " ".join(md.value for md in at.markdown)
    assert "Upload your first dataset" in rendered  # projects empty state


def test_login_failure_shows_friendly_error():
    at = _boot()
    at.text_input(key="login_email").input("ghost@example.com")
    at.text_input(key="login_pw").input("wrongpass99")
    at.button(key="FormSubmitter:login_form-Sign in").set_value(True).run()

    assert not at.exception
    assert any("Invalid email or password" in e.value for e in at.error)
