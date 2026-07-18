"""Shared test fixtures.

Tests run against an isolated tmp environment: SQLite in tmp_path, local
storage in tmp_path, fixed secret key. Settings/engine/storage caches are
reset per test and the schema is created fresh.
"""

import pytest

from dataverse.config import get_settings
from dataverse.models import Base
from dataverse.repositories.base import get_engine, get_session_factory
from dataverse.storage import get_storage


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_storage.cache_clear()


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    _clear_caches()
    Base.metadata.create_all(get_engine())
    yield
    _clear_caches()
