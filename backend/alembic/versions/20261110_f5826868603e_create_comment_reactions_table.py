"""create comment reactions table

Revision ID: f5826868603e
Revises: 8c29362ff5ea
Create Date: 2026-11-10 21:18:55.147831
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5826868603e"
down_revision: str | Sequence[str] | None = "8c29362ff5ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comment_reactions",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column(
            "rated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("value IN (1, -1)", name=op.f("ck_comment_reactions_value")),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comments.id"],
            name=op.f("fk_comment_reactions_comment_id_comments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_comment_reactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("comment_id", "user_id", name=op.f("pk_comment_reactions")),
    )
    op.create_index(
        op.f("ix_comment_reactions_user_id"), "comment_reactions", ["user_id"], unique=False
    )


def downgrade() -> None:
    # The likes go, so do their counts: an upgrade must not start from stale numbers. Count first:
    # DROP TABLE locks comments and users exclusively until commit, and a full UPDATE must not run
    # under that lock. SHARE MODE stops new ratings meanwhile, not reads.
    op.execute("LOCK TABLE comment_reactions IN SHARE MODE")
    op.execute("UPDATE comments SET like_count = 0 WHERE like_count <> 0")
    op.drop_index(op.f("ix_comment_reactions_user_id"), table_name="comment_reactions")
    op.drop_table("comment_reactions")
