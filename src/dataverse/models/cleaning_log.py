"""Immutable record of every applied cleaning action."""

from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dataverse.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CleaningLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cleaning_logs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_name: Mapped[str] = mapped_column(String(50), nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(120))
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rows_affected: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[str] = mapped_column(String(500), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
