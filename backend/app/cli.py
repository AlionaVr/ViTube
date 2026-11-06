"""Admin commands (ADR 0009: roles are managed without a UI).

Run in the api container: docker compose exec api python -m app.cli set-role <email> <role>
"""

import argparse
import asyncio

from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import create_engine, create_sessionmaker
from app.modules.auth import service
from app.modules.users.models import Role


async def set_role(email: str, role: Role) -> None:
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as db:
            await service.set_role(db, email, role)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    set_role_parser = commands.add_parser("set-role", help="give a user a role")
    set_role_parser.add_argument("email")
    set_role_parser.add_argument("role", choices=[role.value for role in Role])
    args = parser.parse_args(argv)

    try:
        asyncio.run(set_role(args.email, Role(args.role)))
    except DomainError as error:
        parser.exit(1, f"error: {error.detail}\n")
    print(f"{args.email}: {args.role}")


if __name__ == "__main__":
    main()
