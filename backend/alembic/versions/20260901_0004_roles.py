"""Create catalog for custom RBAC roles.

Revision ID: 20260901_0004
Revises: 20260830_0003
Create Date: 2026-09-01
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260901_0004"
down_revision: str | None = "20260830_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "roles" in inspector.get_table_names():
        return
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("capabilities", JSONB(), nullable=False, server_default="[]"),
        sa.Column("statewide", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_roles_slug", "roles", ["slug"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "roles" not in inspector.get_table_names():
        return
    op.drop_index("ix_roles_slug", table_name="roles")
    op.drop_table("roles")
