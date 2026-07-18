"""Shared test fixtures.

Tests run against an isolated tmp environment: SQLite in tmp_path, local
storage in tmp_path, fixed secret key. Settings caches are reset per test.
"""

import pytest

from dataverse.config import get_settings
from dataverse.repositories.base import get_engine, get_session_factory


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
