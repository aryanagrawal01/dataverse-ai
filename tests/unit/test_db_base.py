import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from dataverse.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from dataverse.repositories.base import get_engine, session_scope


class _Widget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_widgets"
    name: Mapped[str] = mapped_column(String(50))


def test_session_scope_commits():
    Base.metadata.create_all(get_engine())
    with session_scope() as s:
        s.add(_Widget(name="alpha"))
    with session_scope() as s:
        row = s.execute(select(_Widget)).scalar_one()
        assert row.name == "alpha"
        assert len(row.id) == 36  # uuid string
        assert row.created_at is not None


def test_session_scope_rolls_back_on_error():
    Base.metadata.create_all(get_engine())
    with pytest.raises(RuntimeError), session_scope() as s:
        s.add(_Widget(name="doomed"))
        raise RuntimeError("boom")
    with session_scope() as s:
        names = s.execute(select(_Widget.name)).scalars().all()
        assert "doomed" not in names
