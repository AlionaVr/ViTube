"""add comments is deleted

Revision ID: 517846be4331
Revises: 7b768f9331c8
Create Date: 2026-11-11 21:25:33.722866
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "517846be4331"
down_revision: str | Sequence[str] | None = "7b768f9331c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A constant default: Postgres adds the column without rewriting the table.
    op.add_column(
        "comments",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    # Without the flag, deleted comments would show again: remove them for good (their replies
    # cascade). The counters already leave them out, so they stay right.
    op.execute("DELETE FROM comments WHERE is_deleted")
    op.drop_column("comments", "is_deleted")
