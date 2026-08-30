"""Store watchlist face embeddings.

Revision ID: 20260830_0003
Revises: 20260824_0002
Create Date: 2026-08-30
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260830_0003"
down_revision: str | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("watchlist")}
    if "face_embedding" in columns:
        return
    op.add_column("watchlist", sa.Column("face_embedding", JSONB(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("watchlist")}
    if "face_embedding" in columns:
        op.drop_column("watchlist", "face_embedding")
