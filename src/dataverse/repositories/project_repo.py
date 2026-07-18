"""Project persistence. Every query is scoped by user_id — ownership is
enforced here, not in callers."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataverse.models import DatasetVersion, Project
from dataverse.models.base import utcnow


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_for_user(self, user_id: str) -> list[Project]:
        return list(
            self._s.execute(
                select(Project)
                .where(Project.user_id == user_id, Project.deleted_at.is_(None))
                .order_by(Project.created_at.desc())
            ).scalars()
        )

    def by_id_for_user(self, user_id: str, project_id: str) -> Project | None:
        """Returns None for both 'missing' and 'not owned' — no existence leak."""
        return self._s.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.deleted_at.is_(None),
            )
        ).scalar_one_or_none()

    def create(self, user_id: str, name: str, source_filename: str | None) -> Project:
        project = Project(user_id=user_id, name=name, source_filename=source_filename)
        self._s.add(project)
        self._s.flush()
        return project

    def soft_delete(self, project: Project) -> None:
        project.deleted_at = utcnow()

    def versions(self, project_id: str) -> list[DatasetVersion]:
        return list(
            self._s.execute(
                select(DatasetVersion).where(DatasetVersion.project_id == project_id)
            ).scalars()
        )

    def version_by_kind(self, project_id: str, kind: str) -> DatasetVersion | None:
        return self._s.execute(
            select(DatasetVersion).where(
                DatasetVersion.project_id == project_id, DatasetVersion.kind == kind
            )
        ).scalar_one_or_none()

    def total_bytes_for_user(self, user_id: str) -> int:
        rows = self._s.execute(
            select(DatasetVersion.size_bytes)
            .join(Project, Project.id == DatasetVersion.project_id)
            .where(Project.user_id == user_id, Project.deleted_at.is_(None))
        ).scalars()
        return sum(b or 0 for b in rows)
