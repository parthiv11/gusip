"""Scope cases to a department.

Revision ID: 20260824_0002
Revises: 20260824_0001
Create Date: 2026-08-24
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260824_0002"
down_revision: str | None = "20260824_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("cases")}
    if "department_id" in columns:
        return
    op.add_column("cases", sa.Column("department_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cases_department_id_departments",
        "cases",
        "departments",
        ["department_id"],
        ["id"],
    )
    op.create_index("ix_cases_department_id", "cases", ["department_id"])


def downgrade() -> None:
    op.drop_index("ix_cases_department_id", table_name="cases")
    op.drop_constraint("fk_cases_department_id_departments", "cases", type_="foreignkey")
    op.drop_column("cases", "department_id")
