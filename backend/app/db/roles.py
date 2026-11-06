"""The app's least-privilege DB role (ADR 0010). The migrate job runs this after the migrations.

Run: python -m app.db.roles (as the superuser; needs POSTGRES_APP_PASSWORD).
"""

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import get_settings
from app.db import locks
from app.db.session import create_engine

APP_ROLE = "vitube_app"  # also in compose.yaml: DATABASE_URL of api and worker
SCRAM_ITERATIONS = 4096  # Postgres default

# Each runs on every deploy, so the role is right on a fresh DB and on an existing volume.
SETUP = (
    # Data only: no DDL, no superuser powers.
    f"ALTER ROLE {APP_ROLE} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
    # Stops runaway queries and forgotten transactions.
    f"ALTER ROLE {APP_ROLE} SET statement_timeout = '30s'",
    f"ALTER ROLE {APP_ROLE} SET idle_in_transaction_session_timeout = '60s'",
    # Existing tables and sequences.
    f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
    f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}",
    # Future ones: created by later migrations, which run as this same superuser.
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
    f" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}",
    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}",
    # Migration bookkeeping is not app data.
    f"REVOKE ALL ON alembic_version FROM {APP_ROLE}",
)


def scram_sha256(password: str) -> str:
    """The SCRAM-SHA-256 verifier Postgres stores, built here: the plain password never leaves us.

    Postgres keeps a verifier given in ALTER ROLE ... PASSWORD as is (RFC 5802, RFC 7677).
    """
    if not password.isascii():
        # Postgres normalizes non-ASCII passwords (SASLprep) before hashing; this code doesn't.
        raise ValueError("The app DB password must be ASCII")
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, SCRAM_ITERATIONS)
    stored_key = hashlib.sha256(hmac.digest(salted, b"Client Key", "sha256")).digest()
    server_key = hmac.digest(salted, b"Server Key", "sha256")
    b64 = [base64.b64encode(part).decode() for part in (salt, stored_key, server_key)]
    return f"SCRAM-SHA-256${SCRAM_ITERATIONS}:{b64[0]}${b64[1]}:{b64[2]}"


async def setup_app_role(conn: AsyncConnection, password: str) -> None:
    """Create or update the app role. Idempotent; a new password rotates the old one."""
    await conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": locks.MIGRATIONS})
    if not await conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}):
        await conn.execute(text(f"CREATE ROLE {APP_ROLE}"))
    # ALTER ROLE takes no bind parameters: Postgres quotes the verifier itself (%L).
    set_password = await conn.scalar(
        text(
            "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', CAST(:r AS text), CAST(:v AS text))"
        ),
        {"r": APP_ROLE, "v": scram_sha256(password)},
    )
    # Not text(): the verifier has ":" that text() would read as bind parameters.
    await conn.exec_driver_sql(set_password)
    for statement in SETUP:
        await conn.execute(text(statement))


async def main() -> None:
    password = os.environ.get("POSTGRES_APP_PASSWORD")
    if not password:
        sys.exit("POSTGRES_APP_PASSWORD is not set")
    engine = create_engine(get_settings())
    try:
        async with engine.begin() as conn:
            await setup_app_role(conn, password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
