"""The app's DB role (ADR 0010): what vitube_app may and may not do."""

import pytest
from sqlalchemy import event, make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.roles import APP_ROLE, scram_sha256, setup_app_role

INSUFFICIENT_PRIVILEGE = "42501"

FORBIDDEN = {
    "create a table": "CREATE TABLE intruder (id int)",
    "drop a table": "DROP TABLE users",
    "alter a table": "ALTER TABLE users ADD COLUMN intruder int",
    "truncate a table": "TRUNCATE users",
    "read migration state": "SELECT * FROM alembic_version",
    "change migration state": "UPDATE alembic_version SET version_num = 'x'",
    "run a shell command": "COPY users TO PROGRAM 'id'",
    "create a role": "CREATE ROLE intruder",
    "take a privileged role": "SET ROLE pg_execute_server_program",
    "rewrite the audit log": "UPDATE audit_log SET details = '{}'",
    "erase the audit log": "DELETE FROM audit_log",
}


async def test_app_role_reads_and_writes_data(db: AsyncSession) -> None:
    await db.execute(
        text(
            "INSERT INTO users (email, handle, password_hash)"
            " VALUES ('anna@example.com', 'user-k3j9x2m1', 'hash')"
        )
    )
    await db.execute(text("UPDATE users SET password_hash = 'new'"))
    assert await db.scalar(text("SELECT password_hash FROM users")) == "new"

    await db.execute(text("DELETE FROM users"))
    assert await db.scalar(text("SELECT count(*) FROM users")) == 0


async def test_app_role_can_use_tables_and_sequences_created_later(
    admin_engine: AsyncEngine, db: AsyncSession
) -> None:
    # As a later migration would: the superuser adds a table with a sequence (serial).
    async with admin_engine.begin() as conn:
        await conn.execute(text("CREATE TABLE later_items (id serial PRIMARY KEY, name text)"))
    try:
        new_id = await db.scalar(text("INSERT INTO later_items (name) VALUES ('a') RETURNING id"))
        assert new_id == 1
    finally:
        await db.rollback()
        async with admin_engine.begin() as conn:
            await conn.execute(text("DROP TABLE later_items"))


@pytest.mark.parametrize("statement", FORBIDDEN.values(), ids=list(FORBIDDEN))
async def test_app_role_cannot(db: AsyncSession, statement: str) -> None:
    with pytest.raises(DBAPIError) as error:
        await db.execute(text(statement))

    assert getattr(error.value.orig, "sqlstate", None) == INSUFFICIENT_PRIVILEGE


async def test_app_role_has_no_superpowers_and_has_timeouts(db: AsyncSession) -> None:
    role = await db.execute(
        text(
            "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls"
            " FROM pg_roles WHERE rolname = current_user"
        )
    )

    assert tuple(role.one()) == (APP_ROLE, False, False, False, False, False)
    assert await db.scalar(text("SHOW statement_timeout")) == "30s"
    assert await db.scalar(text("SHOW idle_in_transaction_session_timeout")) == "1min"


def test_non_ascii_password_is_refused() -> None:
    with pytest.raises(ValueError, match="ASCII"):
        scram_sha256("пароль-123")


async def test_redeploy_rotates_the_password_and_sends_only_its_hash(
    admin_engine: AsyncEngine,
) -> None:
    app_url = make_url(str(get_settings().database_url))  # the URL the app connects with
    old_password = app_url.password
    assert old_password
    sent: list[str] = []  # every statement and parameter set that reached Postgres

    def record(conn, cursor, statement, parameters, context, executemany) -> None:
        sent.append(f"{statement} {parameters}")

    async def can_log_in(password: str) -> bool:
        engine = create_async_engine(app_url.set(password=password), poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except DBAPIError:
            return False
        finally:
            await engine.dispose()

    event.listen(admin_engine.sync_engine, "before_cursor_execute", record)
    try:
        for _ in range(2):  # two deploys in a row: the second run must be a no-op
            async with admin_engine.begin() as conn:
                await setup_app_role(conn, "rotated-password")

        assert any("SCRAM-SHA-256$" in line for line in sent)  # the hash went out...
        assert not any("rotated-password" in line for line in sent)  # ...the password didn't
        assert await can_log_in("rotated-password")
        assert not await can_log_in(old_password)
    finally:
        event.remove(admin_engine.sync_engine, "before_cursor_execute", record)
        async with admin_engine.begin() as conn:
            await setup_app_role(conn, old_password)
