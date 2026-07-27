import pytest

from dataverse.config import get_settings


def test_defaults_are_dev_safe():
    s = get_settings()
    assert s.environment == "dev"
    assert s.max_upload_bytes == s.max_upload_mb * 1024 * 1024
    assert not s.llm_configured


def test_prod_rejects_default_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-change-me")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://x/y")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_settings().validate_for_environment()


def test_prod_rejects_sqlite(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", "a-real-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="SQLite"):
        get_settings().validate_for_environment()


def test_llm_configured_flag(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    assert get_settings().llm_configured


def test_llm_base_url_defaults_empty_and_is_configurable(monkeypatch):
    assert get_settings().llm_base_url == ""
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    get_settings.cache_clear()
    assert get_settings().llm_base_url == "https://api.groq.com/openai/v1"
