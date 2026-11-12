"""add users status

Revision ID: f73a3dde8bda
Revises: 517846be4331
Create Date: 2026-11-11 22:05:18.637610
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f73a3dde8bda"
down_revision: str | Sequence[str] | None = "517846be4331"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A constant default: Postgres adds the column without rewriting the table.
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
    )
    # Named here, not derived: a migration must not depend on today's naming convention.
    op.create_check_constraint(
        op.f("ck_users_status"), "users", "status IN ('active', 'banned', 'terminated')"
    )
    op.create_index(
        "ix_users_restricted_id",
        "users",
        ["id"],
        unique=False,
        postgresql_where=sa.text("status <> 'active'"),
    )


def downgrade() -> None:
    # Banned and terminated accounts become active again: the column was the only record.
    op.drop_index(
        "ix_users_restricted_id", table_name="users", postgresql_where=sa.text("status <> 'active'")
    )
    op.drop_column("users", "status")  # its CHECK goes with it
