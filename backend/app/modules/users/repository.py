"""User queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    # citext: the match ignores case.
    return await db.scalar(select(User).where(User.email == email))


async def insert_unless_taken(
    db: AsyncSession, *, email: str, handle: str, password_hash: str
) -> User | None:
    """Insert a user. None if the email or handle is taken: no exception, no savepoint needed."""
    statement = (
        insert(User)
        .values(email=email, handle=handle, password_hash=password_hash)
        .on_conflict_do_nothing()
        .returning(User)
    )
    return await db.scalar(statement)
