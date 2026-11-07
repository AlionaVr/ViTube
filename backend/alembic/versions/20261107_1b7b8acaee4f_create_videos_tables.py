"""create videos tables

Revision ID: 1b7b8acaee4f
Revises: 73875e0933c4
Create Date: 2026-11-07 22:25:43.068534
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1b7b8acaee4f"
down_revision: str | Sequence[str] | None = "73875e0933c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("public_id", sa.String(length=11), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("visibility", sa.String(length=16), server_default="private", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="uploading", nullable=False),
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processing_attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("like_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("comment_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "public_id ~ '^[A-Za-z0-9_-]{11}$'", name=op.f("ck_videos_public_id_format")
        ),
        sa.CheckConstraint(
            "char_length(description) <= 5000", name=op.f("ck_videos_description_length")
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) >= 1 AND char_length(title) <= 100",
            name=op.f("ck_videos_title_length"),
        ),
        sa.CheckConstraint(
            "char_length(error_message) <= 1000", name=op.f("ck_videos_error_message_length")
        ),
        sa.CheckConstraint("duration_sec >= 0", name=op.f("ck_videos_duration_sec_not_negative")),
        sa.CheckConstraint(
            "status <> 'ready' OR duration_sec IS NOT NULL",
            name=op.f("ck_videos_ready_has_duration"),
        ),
        sa.CheckConstraint(
            "(status = 'failed') = (error_message IS NOT NULL)",
            name=op.f("ck_videos_error_message_iff_failed"),
        ),
        sa.CheckConstraint(
            "processing_attempts >= 0", name=op.f("ck_videos_processing_attempts_not_negative")
        ),
        sa.CheckConstraint(
            "view_count >= 0 AND like_count >= 0 AND comment_count >= 0",
            name=op.f("ck_videos_counters_not_negative"),
        ),
        # Named here, not derived: a migration must not depend on today's naming convention.
        sa.CheckConstraint(
            "visibility IN ('public', 'unlisted', 'private')", name=op.f("ck_videos_visibility")
        ),
        sa.CheckConstraint(
            "status IN ('uploading', 'uploaded', 'processing', 'ready', 'failed')",
            name=op.f("ck_videos_status"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_videos_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_videos")),
        sa.UniqueConstraint("public_id", name=op.f("uq_videos_public_id")),
    )
    op.create_index(op.f("ix_videos_owner_id"), "videos", ["owner_id"], unique=False)
    # Every status change stamps status_changed_at, whoever writes it: the sweeper relies on it.
    # alembic check doesn't compare triggers; tests cover this one.
    op.execute(
        """
        CREATE FUNCTION videos_touch_status_changed_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.status_changed_at := now();
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER videos_status_changed_at
        BEFORE UPDATE OF status ON videos
        FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
        EXECUTE FUNCTION videos_touch_status_changed_at()
        """
    )
    op.create_table(
        "video_access",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_video_access_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name=op.f("fk_video_access_video_id_videos"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("video_id", "user_id", name=op.f("pk_video_access")),
    )
    op.create_index(op.f("ix_video_access_user_id"), "video_access", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_video_access_user_id"), table_name="video_access")
    op.drop_table("video_access")
    op.execute("DROP TRIGGER videos_status_changed_at ON videos")
    op.execute("DROP FUNCTION videos_touch_status_changed_at()")
    op.drop_index(op.f("ix_videos_owner_id"), table_name="videos")
    op.drop_table("videos")
