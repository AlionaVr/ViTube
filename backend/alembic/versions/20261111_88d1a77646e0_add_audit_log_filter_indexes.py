"""add audit log filter indexes

Revision ID: 88d1a77646e0
Revises: f73a3dde8bda
Create Date: 2026-11-11 22:48:45.289619
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "88d1a77646e0"
down_revision: str | Sequence[str] | None = "f73a3dde8bda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The admins' audit log filters, each newest first.
    op.create_index("ix_audit_log_action_id", "audit_log", ["action", "id"], unique=False)
    op.create_index("ix_audit_log_actor_id_id", "audit_log", ["actor_id", "id"], unique=False)
    op.create_index(
        "ix_audit_log_cli_id",
        "audit_log",
        ["id"],
        unique=False,
        postgresql_where=sa.text("source = 'cli'"),
    )
    op.create_index(
        "ix_audit_log_target_type_target_id_id",
        "audit_log",
        ["target_type", "target_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_target_type_target_id_id", table_name="audit_log")
    op.drop_index(
        "ix_audit_log_cli_id", table_name="audit_log", postgresql_where=sa.text("source = 'cli'")
    )
    op.drop_index("ix_audit_log_actor_id_id", table_name="audit_log")
    op.drop_index("ix_audit_log_action_id", table_name="audit_log")
