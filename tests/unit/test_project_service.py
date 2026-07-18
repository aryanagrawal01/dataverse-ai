import pytest

from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.services import auth_service, project_service
from dataverse.storage import get_storage
from dataverse.utils.errors import NotFoundError, ValidationError


@pytest.fixture
def user_a():
    return auth_service.register("a@example.com", "password9").user


@pytest.fixture
def user_b():
    return auth_service.register("b@example.com", "password9").user


def _make_project(user_id: str, name: str = "Q2 Sales") -> str:
    with session_scope() as s:
        return ProjectRepository(s).create(user_id, name, "sales.csv").id


def test_list_starts_empty(user_a):
    assert project_service.list_projects(user_a.id) == []


def test_create_and_get(user_a):
    pid = _make_project(user_a.id)
    project = project_service.get_project(user_a.id, pid)
    assert project.name == "Q2 Sales"
    assert project.status == "uploaded"


def test_ownership_isolation(user_a, user_b):
    """User B must not see, rename, or delete user A's project — and the
    error must be indistinguishable from 'does not exist'."""
    pid = _make_project(user_a.id)
    with pytest.raises(NotFoundError):
        project_service.get_project(user_b.id, pid)
    with pytest.raises(NotFoundError):
        project_service.rename_project(user_b.id, pid, "hacked")
    with pytest.raises(NotFoundError):
        project_service.delete_project(user_b.id, pid)
    assert [p.id for p in project_service.list_projects(user_b.id)] == []
    assert project_service.get_project(user_a.id, pid).name == "Q2 Sales"


def test_rename(user_a):
    pid = _make_project(user_a.id)
    renamed = project_service.rename_project(user_a.id, pid, "  Renamed  ")
    assert renamed.name == "Renamed"


def test_rename_rejects_empty_and_too_long(user_a):
    pid = _make_project(user_a.id)
    with pytest.raises(ValidationError):
        project_service.rename_project(user_a.id, pid, "   ")
    with pytest.raises(ValidationError):
        project_service.rename_project(user_a.id, pid, "x" * 121)


def test_delete_removes_from_list_and_purges_artifacts(user_a):
    pid = _make_project(user_a.id)
    storage = get_storage()
    key = f"{user_a.id}/{pid}/raw.parquet"
    storage.put(key, b"fake-parquet-bytes")
    with session_scope() as s:
        from dataverse.models import DatasetVersion

        s.add(DatasetVersion(project_id=pid, kind="raw", storage_key=key, size_bytes=18))

    project_service.delete_project(user_a.id, pid)

    assert project_service.list_projects(user_a.id) == []
    assert not storage.exists(key)
    with pytest.raises(NotFoundError):
        project_service.get_project(user_a.id, pid)


def test_storage_usage_counts_versions(user_a):
    pid = _make_project(user_a.id)
    with session_scope() as s:
        from dataverse.models import DatasetVersion

        s.add(DatasetVersion(project_id=pid, kind="raw", storage_key="k1", size_bytes=1000))
        s.add(DatasetVersion(project_id=pid, kind="cleaned", storage_key="k2", size_bytes=500))
    usage = project_service.storage_usage(user_a.id)
    assert usage.used_bytes == 1500
    assert usage.quota_bytes > 0
