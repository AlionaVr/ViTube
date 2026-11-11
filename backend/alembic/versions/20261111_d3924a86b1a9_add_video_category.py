"""add video category

Revision ID: d3924a86b1a9
Revises: c45a948564d0
Create Date: 2026-11-11 14:17:37.333225
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3924a86b1a9"
down_revision: str | Sequence[str] | None = "c45a948564d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = (
    "film",
    "autos",
    "music",
    "pets",
    "sports",
    "travel",
    "gaming",
    "people",
    "comedy",
    "entertainment",
    "news",
    "howto",
    "education",
    "science",
    "nonprofits",
)


def upgrade() -> None:
    # A constant default: Postgres fills existing rows without rewriting the table.
    op.add_column(
        "videos",
        sa.Column("category", sa.String(length=16), server_default="people", nullable=False),
    )
    # Named here, not derived: a migration must not depend on today's naming convention.
    op.create_check_constraint(
        op.f("ck_videos_category"),
        "videos",
        "category IN (" + ", ".join(f"'{name}'" for name in CATEGORIES) + ")",
    )
    op.create_index(
        "ix_videos_listed_category_id",
        "videos",
        ["category", "id"],
        unique=False,
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_videos_listed_category_id",
        table_name="videos",
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )
    op.drop_constraint(op.f("ck_videos_category"), "videos", type_="check")
    op.drop_column("videos", "category")
