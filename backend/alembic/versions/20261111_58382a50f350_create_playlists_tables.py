"""create playlists tables

Revision ID: 58382a50f350
Revises: 8e2766efbe5f
Create Date: 2026-11-11 20:47:55.432850
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "58382a50f350"
down_revision: str | Sequence[str] | None = "8e2766efbe5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playlists",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "visibility",
            sa.Enum(
                "public",
                "unlisted",
                "private",
                name="visibility",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            server_default="private",
            nullable=False,
        ),
        sa.Column("video_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) >= 1 AND char_length(title) <= 150",
            name=op.f("ck_playlists_title_length"),
        ),
        sa.CheckConstraint(
            "char_length(description) <= 5000", name=op.f("ck_playlists_description_length")
        ),
        sa.CheckConstraint(
            "video_count BETWEEN 0 AND 5000", name=op.f("ck_playlists_video_count_range")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_playlists_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_playlists")),
    )
    op.create_index("ix_playlists_owner_id_id", "playlists", ["owner_id", "id"], unique=False)
    op.create_table(
        "playlist_items",
        sa.Column("playlist_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_playlist_items_position_not_negative")),
        sa.ForeignKeyConstraint(
            ["playlist_id"],
            ["playlists.id"],
            name=op.f("fk_playlist_items_playlist_id_playlists"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name=op.f("fk_playlist_items_video_id_videos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("playlist_id", "video_id", name=op.f("pk_playlist_items")),
        sa.UniqueConstraint(
            "playlist_id",
            "position",
            deferrable=True,
            initially="IMMEDIATE",
            name=op.f("uq_playlist_items_playlist_id_position"),
        ),
    )
    op.create_index(
        op.f("ix_playlist_items_video_id"), "playlist_items", ["video_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_playlist_items_video_id"), table_name="playlist_items")
    op.drop_table("playlist_items")
    op.drop_index("ix_playlists_owner_id_id", table_name="playlists")
    op.drop_table("playlists")
