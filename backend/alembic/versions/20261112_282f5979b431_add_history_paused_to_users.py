"""add history paused to users

Revision ID: 282f5979b431
Revises: f96a27b425e6
Create Date: 2026-11-12 19:02:07.516374
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "282f5979b431"
down_revision: str | Sequence[str] | None = "f96a27b425e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("history_paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "history_paused")
