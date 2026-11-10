"""create comments table

Revision ID: 8c29362ff5ea
Revises: adee0dfb74ad
Create Date: 2026-11-10 01:29:41.514757
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8c29362ff5ea"
down_revision: str | Sequence[str] | None = "adee0dfb74ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("like_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reply_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(text)) >= 1 AND char_length(text) <= 10000",
            name=op.f("ck_comments_text_length"),
        ),
        sa.CheckConstraint(
            "like_count >= 0 AND reply_count >= 0", name=op.f("ck_comments_counters_not_negative")
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR reply_count = 0", name=op.f("ck_comments_only_roots_have_replies")
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_comments_author_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["comments.id"],
            name=op.f("fk_comments_parent_id_comments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name=op.f("fk_comments_video_id_videos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"], unique=False)
    op.create_index(
        "ix_comments_parent_id_id",
        "comments",
        ["parent_id", "id"],
        unique=False,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )
    op.create_index(
        "ix_comments_video_id_like_count_id",
        "comments",
        ["video_id", "like_count", "id"],
        unique=False,
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(
        "ix_comments_video_id_parent_id_id",
        "comments",
        ["video_id", "parent_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_comments_video_id_parent_id_id", table_name="comments")
    op.drop_index(
        "ix_comments_video_id_like_count_id",
        table_name="comments",
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.drop_index(
        "ix_comments_parent_id_id",
        table_name="comments",
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_comments_author_id"), table_name="comments")
    op.drop_table("comments")
    # The comments are gone, so are their counts: an upgrade must not start from stale numbers.
    op.execute("UPDATE videos SET comment_count = 0 WHERE comment_count <> 0")
