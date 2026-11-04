"""baseline: Postgres extensions

Revision ID: e076a883e834
Revises:
Create Date: 2026-11-04 23:33:12.732980
"""

from alembic import op
from collections.abc import Sequence

revision: str = "e076a883e834"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # citext: case-insensitive email and handle. pg_trgm: typo-tolerant search (ADR 0007).
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS citext")
