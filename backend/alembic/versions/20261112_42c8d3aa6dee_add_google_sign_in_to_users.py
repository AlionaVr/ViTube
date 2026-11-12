"""add google sign in to users

Revision ID: 42c8d3aa6dee
Revises: eda018946747
Create Date: 2026-11-12 21:36:30.488144
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "42c8d3aa6dee"
down_revision: str | Sequence[str] | None = "eda018946747"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.Text(), nullable=True))
    op.create_unique_constraint(op.f("uq_users_google_sub"), "users", ["google_sub"])
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint(
        op.f("ck_users_has_credentials"),
        "users",
        "password_hash IS NOT NULL OR google_sub IS NOT NULL",
    )


def downgrade() -> None:
    # Fails while Google-only accounts exist: they have no password to keep, and dropping them
    # would lose data.
    op.drop_constraint(op.f("ck_users_has_credentials"), "users", type_="check")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_constraint(op.f("uq_users_google_sub"), "users", type_="unique")
    op.drop_column("users", "google_sub")
