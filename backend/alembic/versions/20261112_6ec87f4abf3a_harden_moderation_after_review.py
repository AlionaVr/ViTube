"""harden moderation after review

Revision ID: 6ec87f4abf3a
Revises: 88d1a77646e0
Create Date: 2026-11-12 00:46:00.924328
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6ec87f4abf3a"
down_revision: str | Sequence[str] | None = "88d1a77646e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The account each entry is about, kept on the entry: the filter no longer needs the video
    # or comment row, which may be gone. Rows whose target is gone already stay NULL.
    op.add_column("audit_log", sa.Column("subject_user_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE audit_log AS entry SET subject_user_id = CASE entry.target_type
            WHEN 'user' THEN entry.target_id
            WHEN 'video' THEN (SELECT owner_id FROM videos WHERE id = entry.target_id)
            WHEN 'comment' THEN (SELECT author_id FROM comments WHERE id = entry.target_id)
        END
        """
    )
    op.drop_index(op.f("ix_audit_log_target_type_target_id_id"), table_name="audit_log")
    op.create_index(
        "ix_audit_log_subject_user_id_id", "audit_log", ["subject_user_id", "id"], unique=False
    )
    # Sessions started before a ban stop for good, also after a reinstatement.
    op.add_column(
        "users", sa.Column("sessions_valid_after", sa.DateTime(timezone=True), nullable=True)
    )
    # Admins can't be restricted, so a restricted account can't become an admin.
    op.create_check_constraint(
        op.f("ck_users_admin_active"), "users", "role <> 'admin' OR status = 'active'"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_admin_active"), "users", type_="check")
    op.drop_column("users", "sessions_valid_after")
    op.drop_index("ix_audit_log_subject_user_id_id", table_name="audit_log")
    op.create_index(
        op.f("ix_audit_log_target_type_target_id_id"),
        "audit_log",
        ["target_type", "target_id", "id"],
        unique=False,
    )
    op.drop_column("audit_log", "subject_user_id")
