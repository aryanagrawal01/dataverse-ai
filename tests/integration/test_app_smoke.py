"""E2E smoke: the Streamlit app script must execute without exceptions."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "app.py")


def test_app_boots_without_exception():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"App raised: {at.exception}"


def test_landing_renders_brand_and_no_errors():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.error  # no st.error boxes on a clean boot
    rendered = " ".join(md.value for md in at.markdown)
    assert "DataVerse" in rendered
