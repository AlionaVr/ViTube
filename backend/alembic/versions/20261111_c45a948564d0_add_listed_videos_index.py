"""add listed videos index

Revision ID: c45a948564d0
Revises: f5826868603e
Create Date: 2026-11-11 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c45a948564d0"
down_revision: str | Sequence[str] | None = "f5826868603e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_videos_listed_id",
        "videos",
        ["id"],
        unique=False,
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_videos_listed_id",
        table_name="videos",
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )
