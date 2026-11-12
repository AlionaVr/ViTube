"""index liked videos by user and like time

Revision ID: eda018946747
Revises: 282f5979b431
Create Date: 2026-11-12 21:27:22.790844
"""

from collections.abc import Sequence

from alembic import op

revision: str = "eda018946747"
down_revision: str | Sequence[str] | None = "282f5979b431"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Liked videos, newest first. Its user_id prefix serves the cascade from users, as the old
    # index did; created first, so a cascade never runs without one.
    op.create_index(
        "ix_video_reactions_user_id_rated_at_video_id",
        "video_reactions",
        ["user_id", "rated_at", "video_id"],
    )
    op.drop_index("ix_video_reactions_user_id", table_name="video_reactions")


def downgrade() -> None:
    op.create_index("ix_video_reactions_user_id", "video_reactions", ["user_id"])
    op.drop_index("ix_video_reactions_user_id_rated_at_video_id", table_name="video_reactions")
