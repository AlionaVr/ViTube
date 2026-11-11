"""add hidden videos index

Revision ID: 7b768f9331c8
Revises: a917fc5b6fa4
Create Date: 2026-11-11 21:03:06.837812
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b768f9331c8"
down_revision: str | Sequence[str] | None = "a917fc5b6fa4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_videos_hidden_id",
        "videos",
        ["id"],
        unique=False,
        postgresql_where=sa.text("is_hidden"),
    )


def downgrade() -> None:
    op.drop_index("ix_videos_hidden_id", table_name="videos", postgresql_where=sa.text("is_hidden"))
