"""baseline: empty schema

Revision ID: c42034336420
Revises: 
Create Date: 2026-07-18 13:48:51.608616
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'c42034336420'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
