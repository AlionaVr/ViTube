"""create users table

Revision ID: 73875e0933c4
Revises: e076a883e834
Create Date: 2026-11-06 00:06:20.713529
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "73875e0933c4"
down_revision: str | Sequence[str] | None = "e076a883e834"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("handle", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "handle::text ~ '^[a-z0-9._-]{3,30}$'", name=op.f("ck_users_handle_format")
        ),
        # Named here, not derived: a migration must not depend on today's naming convention.
        sa.CheckConstraint("role IN ('user', 'moderator', 'admin')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("handle", name=op.f("uq_users_handle")),
    )


def downgrade() -> None:
    op.drop_table("users")
