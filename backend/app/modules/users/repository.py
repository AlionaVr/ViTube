"""User queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def lock(db: AsyncSession, user_id: UUID) -> None:
    """SELECT ... FOR UPDATE: other transactions that lock this user wait until ours ends."""
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    # citext: the match ignores case.
    return await db.scalar(select(User).where(User.email == email))


async def get_by_handle(db: AsyncSession, handle: str) -> User | None:
    # citext: the match ignores case.
    return await db.scalar(select(User).where(User.handle == handle))


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
