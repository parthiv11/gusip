"""Create the initial GUSIP schema.

Revision ID: 20260824_0001
Revises:
Create Date: 2026-08-24
"""
from typing import Sequence

from alembic import op

from app import models  # noqa: F401
from app.db import Base

revision: str = "20260824_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_open_watchlist_camera "
        "ON alerts (watchlist_id, camera_id) WHERE status = 'new'"
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
