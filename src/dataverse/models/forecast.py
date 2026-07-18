"""Forecast and report persistence."""

from typing import Any

from sqlalchemy import JSON, BigInteger, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from dataverse.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Forecast(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forecasts"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_column: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False)
    horizon: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    model_name: Mapped[str] = mapped_column(String(40), nullable=False)
    backtest_mape: Mapped[float | None] = mapped_column(Numeric(8, 3))
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
