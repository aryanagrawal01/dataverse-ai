"""Project CRUD. All methods take user_id first and enforce ownership."""

from dataverse.config import get_settings
from dataverse.repositories.base import session_scope
from dataverse.repositories.project_repo import ProjectRepository
from dataverse.schemas.project import ProjectSummary, StorageUsage
from dataverse.storage import get_storage
from dataverse.utils.errors import NotFoundError, ValidationError
from dataverse.utils.logging import get_logger

log = get_logger(__name__)


def list_projects(user_id: str) -> list[ProjectSummary]:
    with session_scope() as s:
        return [
            ProjectSummary.model_validate(p) for p in ProjectRepository(s).list_for_user(user_id)
        ]


def get_project(user_id: str, project_id: str) -> ProjectSummary:
    with session_scope() as s:
        project = ProjectRepository(s).by_id_for_user(user_id, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        return ProjectSummary.model_validate(project)


def rename_project(user_id: str, project_id: str, new_name: str) -> ProjectSummary:
    new_name = new_name.strip()
    if not new_name or len(new_name) > 120:
        raise ValidationError(
            f"bad project name length={len(new_name)}",
            user_message="Project names must be 1–120 characters.",
        )
    with session_scope() as s:
        project = ProjectRepository(s).by_id_for_user(user_id, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        project.name = new_name
        result = ProjectSummary.model_validate(project)
    log.info("project.renamed", project_id=project_id)
    return result


def delete_project(user_id: str, project_id: str) -> None:
    """Soft-delete the row now; purge storage artifacts immediately.

    The soft-deleted row provides an audit trail; artifacts are removed at once
    so quota is freed immediately.
    """
    storage = get_storage()
    with session_scope() as s:
        repo = ProjectRepository(s)
        project = repo.by_id_for_user(user_id, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found for user {user_id}")
        keys = [v.storage_key for v in repo.versions(project_id)]
        repo.soft_delete(project)
    for key in keys:
        storage.delete(key)
    log.info("project.deleted", project_id=project_id, artifacts_removed=len(keys))


def storage_usage(user_id: str) -> StorageUsage:
    settings = get_settings()
    with session_scope() as s:
        used = ProjectRepository(s).total_bytes_for_user(user_id)
    return StorageUsage(used_bytes=used, quota_bytes=settings.user_quota_mb * 1024 * 1024)
