"""create video reactions table

Revision ID: adee0dfb74ad
Revises: 1b7b8acaee4f
Create Date: 2026-11-10 00:35:50.088120
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "adee0dfb74ad"
down_revision: str | Sequence[str] | None = "1b7b8acaee4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_reactions",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column(
            "rated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("value IN (1, -1)", name=op.f("ck_video_reactions_value")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_video_reactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name=op.f("fk_video_reactions_video_id_videos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("video_id", "user_id", name=op.f("pk_video_reactions")),
    )
    op.create_index(
        op.f("ix_video_reactions_user_id"), "video_reactions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_video_reactions_user_id"), table_name="video_reactions")
    op.drop_table("video_reactions")
    # The likes are gone, so are their counts: an upgrade must not start from stale numbers.
    op.execute("UPDATE videos SET like_count = 0 WHERE like_count <> 0")
