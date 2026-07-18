"""Project DTOs crossing the service boundary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    source_filename: str | None
    health_score: int | None
    row_count: int | None
    column_count: int | None
    created_at: datetime


class StorageUsage(BaseModel):
    used_bytes: int
    quota_bytes: int

    @property
    def used_fraction(self) -> float:
        return min(1.0, self.used_bytes / self.quota_bytes) if self.quota_bytes else 0.0
