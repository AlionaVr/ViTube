"""add moderation reports and audit log

Revision ID: a917fc5b6fa4
Revises: 89f805433b25
Create Date: 2026-11-11 19:57:22.129420
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a917fc5b6fa4"
down_revision: str | Sequence[str] | None = "89f805433b25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(source = 'api') = (actor_id IS NOT NULL)", name=op.f("ck_audit_log_actor_iff_api")
        ),
        # Named here, not derived: a migration must not depend on today's naming convention.
        sa.CheckConstraint("source IN ('api', 'cli')", name=op.f("ck_audit_log_source")),
        sa.CheckConstraint(
            "action IN ('hide_video', 'restore_video', 'dismiss_video', 'delete_comment',"
            " 'dismiss_comment', 'set_user_status', 'set_user_role')",
            name=op.f("ck_audit_log_action"),
        ),
        sa.CheckConstraint(
            "target_type IN ('video', 'comment', 'user')", name=op.f("ck_audit_log_target_type")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    # The app role may not UPDATE or DELETE it: app.db.roles revokes that after migrations.

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("details", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(video_id, comment_id) = 1", name=op.f("ck_reports_one_target")
        ),
        sa.CheckConstraint("char_length(details) <= 500", name=op.f("ck_reports_details_length")),
        sa.CheckConstraint(
            "(status = 'open') = (resolved_at IS NULL)", name=op.f("ck_reports_resolved_iff_closed")
        ),
        sa.CheckConstraint(
            "reason IN ('sexual', 'violent', 'hateful', 'harassment', 'harmful',"
            " 'misinformation', 'child_abuse', 'terrorism', 'spam', 'legal')",
            name=op.f("ck_reports_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'actioned', 'dismissed')", name=op.f("ck_reports_status")
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            name=op.f("fk_reports_reporter_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name=op.f("fk_reports_video_id_videos"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["comments.id"],
            name=op.f("fk_reports_comment_id_comments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name=op.f("fk_reports_resolved_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_reporter_id"), "reports", ["reporter_id"], unique=False)
    op.create_index(op.f("ix_reports_video_id"), "reports", ["video_id"], unique=False)
    op.create_index(op.f("ix_reports_comment_id"), "reports", ["comment_id"], unique=False)
    op.create_index(op.f("ix_reports_resolved_by"), "reports", ["resolved_by"], unique=False)
    op.create_index(
        "ix_reports_video_id_reporter_id_open",
        "reports",
        ["video_id", "reporter_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND video_id IS NOT NULL"),
    )
    op.create_index(
        "ix_reports_comment_id_reporter_id_open",
        "reports",
        ["comment_id", "reporter_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND comment_id IS NOT NULL"),
    )
    op.create_index(
        "ix_reports_open_id",
        "reports",
        ["id"],
        unique=False,
        postgresql_where=sa.text("status = 'open'"),
    )

    # A constant default: Postgres adds the column without rewriting the table.
    op.add_column(
        "videos",
        sa.Column("is_hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    # Hidden videos become visible again: the column was the only record of hiding.
    op.drop_column("videos", "is_hidden")
    op.drop_table("reports")  # its indexes go with it
    op.drop_table("audit_log")
