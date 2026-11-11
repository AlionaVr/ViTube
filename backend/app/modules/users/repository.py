"""User queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def lock(db: AsyncSession, user_id: UUID) -> None:
    """SELECT ... FOR NO KEY UPDATE: other transactions that lock this user wait until ours ends.

    Not FOR UPDATE: that would also block foreign key checks (KEY SHARE) of rows that point at
    the user, e.g. someone subscribing to them.
    """
    await db.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))


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


async def get_for_write(db: AsyncSession, user_id: UUID) -> User | None:
    """The user, read FOR KEY SHARE and held until the transaction ends.

    A status change locks the user FOR UPDATE first (lock_for_status), which waits for this
    lock: writes already under way finish first, and the ones after it see the new status.
    """
    query = (
        select(User)
        .where(User.id == user_id)
        .with_for_update(read=True, key_share=True)
        .execution_options(populate_existing=True)  # the row as locked, not as cached
    )
    return await db.scalar(query)


async def lock_for_status(db: AsyncSession, user_id: UUID) -> User | None:
    """The user, FOR UPDATE: waits for their writes under way (see get_for_write), and makes
    role and status changes run one at a time."""
    query = (
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return await db.scalar(query)
