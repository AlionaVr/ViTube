"""Admin commands (ADR 0009): roles, and bans as in the moderation page.

Run in the api container: docker compose exec api python -m app.cli <command> ...
Each change goes to the audit log with source "cli" and the admin named by --by: required to
restrict an account; set-role takes it too, but makes the first admin without one.
"""

import argparse
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import DomainError, NotFound
from app.core.redis import create_redis
from app.db.session import create_engine, create_sessionmaker
from app.modules.audit.repository import Actor
from app.modules.auth import service
from app.modules.auth.config import get_auth_settings
from app.modules.auth.sessions import SessionStore
from app.modules.moderation import service as moderation
from app.modules.users import repository as users
from app.modules.users.models import Role, UserStatus


async def actor(db: AsyncSession, by: str | None) -> Actor:
    """--by names the admin running the command. Not proof of who it is: shell access is."""
    if by is not None:
        admin = await users.get_by_email(db, by)
        if admin is None or admin.role is not Role.ADMIN:
            raise NotFound("No admin with this email (--by)")
    return Actor.cli(by)


async def set_role(email: str, role: Role, by: str | None) -> None:
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as db:
            await service.set_role(db, await actor(db, by), email, role)
    finally:
        await engine.dispose()


async def set_status(email: str, status: UserStatus, by: str, reason: str) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    redis = create_redis(settings)
    try:
        async with create_sessionmaker(engine)() as db:
            user = await users.get_by_email(db, email)
            if user is None:
                raise NotFound("No user with this email")
            sessions = SessionStore(redis, get_auth_settings().session_secret)
            await moderation.set_status(db, sessions, await actor(db, by), user.id, status, reason)
    finally:
        await redis.aclose()
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    by_help = "the admin running this, for the audit log"

    set_role_parser = commands.add_parser("set-role", help="give a user a role")
    set_role_parser.add_argument("email")
    set_role_parser.add_argument("role", choices=[role.value for role in Role])
    set_role_parser.add_argument("--by", metavar="EMAIL", help=f"{by_help} (none for the first)")

    set_status_parser = commands.add_parser(
        "set-status", help="ban, terminate or reinstate (active) an account"
    )
    set_status_parser.add_argument("email")
    set_status_parser.add_argument("status", choices=[status.value for status in UserStatus])
    set_status_parser.add_argument("--by", metavar="EMAIL", required=True, help=by_help)
    set_status_parser.add_argument("--reason", default="", help="why, for the audit log")
    args = parser.parse_args(argv)

    try:
        if args.command == "set-role":
            asyncio.run(set_role(args.email, Role(args.role), args.by))
            print(f"{args.email}: {args.role}")
        else:
            asyncio.run(set_status(args.email, UserStatus(args.status), args.by, args.reason))
            print(f"{args.email}: {args.status}")
    except DomainError as error:
        parser.exit(1, f"error: {error.detail}\n")


if __name__ == "__main__":
    main()
