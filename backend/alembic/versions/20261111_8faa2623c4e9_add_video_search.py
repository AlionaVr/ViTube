"""add video search

Revision ID: 8faa2623c4e9
Revises: d3924a86b1a9
Create Date: 2026-11-11 14:39:29.562331
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8faa2623c4e9"
down_revision: str | Sequence[str] | None = "d3924a86b1a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A stored generated column rewrites the table once: quick at this size.
    op.add_column(
        "videos",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', title), 'A')"
                " || setweight(to_tsvector('english', description), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_videos_listed_search_vector",
        "videos",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )
    op.create_index(
        "ix_videos_listed_title_trgm",
        "videos",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_videos_listed_title_trgm",
        table_name="videos",
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )
    op.drop_index(
        "ix_videos_listed_search_vector",
        table_name="videos",
        postgresql_using="gin",
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )
    op.drop_column("videos", "search_vector")
