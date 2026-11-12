"""create watch history table

Revision ID: f96a27b425e6
Revises: 6ec87f4abf3a
Create Date: 2026-11-12 18:07:20.878473
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f96a27b425e6"
down_revision: str | Sequence[str] | None = "6ec87f4abf3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watch_history",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("position_sec", sa.Integer(), nullable=False),
        sa.Column(
            "watched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position_sec >= 0", name=op.f("ck_watch_history_position_sec_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_watch_history_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name=op.f("fk_watch_history_video_id_videos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "video_id", name=op.f("pk_watch_history")),
    )
    op.create_index(
        "ix_watch_history_user_id_watched_at_video_id",
        "watch_history",
        ["user_id", "watched_at", "video_id"],
        unique=False,
    )
    op.create_index(op.f("ix_watch_history_video_id"), "watch_history", ["video_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_watch_history_video_id"), table_name="watch_history")
    op.drop_index("ix_watch_history_user_id_watched_at_video_id", table_name="watch_history")
    op.drop_table("watch_history")
