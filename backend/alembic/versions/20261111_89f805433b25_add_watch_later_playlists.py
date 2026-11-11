"""add watch later playlists

Revision ID: 89f805433b25
Revises: 58382a50f350
Create Date: 2026-11-11 22:33:38.998576
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "89f805433b25"
down_revision: str | Sequence[str] | None = "58382a50f350"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Every user gets a Watch later the moment their row is inserted, whoever inserts it (sign-up,
# seed, CLI, tests). alembic check doesn't compare triggers; tests cover this one.
CREATE_FUNCTION = """
CREATE FUNCTION users_create_watch_later() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO playlists (owner_id, title, kind, visibility)
    VALUES (NEW.id, 'Watch later', 'watch_later', 'private');
    RETURN NEW;
END
$$
"""
CREATE_TRIGGER = """
CREATE TRIGGER users_watch_later
AFTER INSERT ON users
FOR EACH ROW EXECUTE FUNCTION users_create_watch_later()
"""


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column(
            "kind",
            sa.Enum(
                "user",
                "watch_later",
                name="kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            server_default="user",
            nullable=False,
        ),
    )
    op.create_index(
        "uq_playlists_owner_id_watch_later",
        "playlists",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'watch_later'"),
    )
    # alembic doesn't detect CHECKs on an existing table.
    op.create_check_constraint(
        op.f("ck_playlists_watch_later_private"),
        "playlists",
        "kind <> 'watch_later' OR visibility = 'private'",
    )
    op.execute(CREATE_FUNCTION)
    op.execute(CREATE_TRIGGER)
    # Users from before this migration get theirs now.
    op.execute(
        "INSERT INTO playlists (owner_id, title, kind, visibility)"
        " SELECT id, 'Watch later', 'watch_later', 'private' FROM users"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER users_watch_later ON users")
    op.execute("DROP FUNCTION users_create_watch_later()")
    op.execute("DELETE FROM playlists WHERE kind = 'watch_later'")  # their items go by cascade
    op.drop_constraint(op.f("ck_playlists_watch_later_private"), "playlists", type_="check")
    op.drop_index(
        "uq_playlists_owner_id_watch_later",
        table_name="playlists",
        postgresql_where=sa.text("kind = 'watch_later'"),
    )
    op.drop_column("playlists", "kind")
