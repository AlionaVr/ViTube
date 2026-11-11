"""create subscriptions table

Revision ID: 8e2766efbe5f
Revises: 8faa2623c4e9
Create Date: 2026-11-11 19:29:56.824542
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8e2766efbe5f"
down_revision: str | Sequence[str] | None = "8faa2623c4e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("subscriber_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("subscriber_id <> channel_id", name=op.f("ck_subscriptions_not_self")),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["users.id"],
            name=op.f("fk_subscriptions_channel_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"],
            ["users.id"],
            name=op.f("fk_subscriptions_subscriber_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("subscriber_id", "channel_id", name=op.f("pk_subscriptions")),
    )
    op.create_index(
        op.f("ix_subscriptions_channel_id"), "subscriptions", ["channel_id"], unique=False
    )
    op.add_column(
        "users", sa.Column("subscriber_count", sa.Integer(), server_default="0", nullable=False)
    )
    # alembic doesn't detect CHECKs on an existing table.
    op.create_check_constraint(
        op.f("ck_users_subscriber_count_not_negative"), "users", "subscriber_count >= 0"
    )
    op.create_index(
        "ix_videos_listed_owner_id_id",
        "videos",
        ["owner_id", "id"],
        unique=False,
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_videos_listed_owner_id_id",
        table_name="videos",
        postgresql_where=sa.text("visibility = 'public' AND status = 'ready'"),
    )
    op.drop_column("users", "subscriber_count")
    op.drop_index(op.f("ix_subscriptions_channel_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
