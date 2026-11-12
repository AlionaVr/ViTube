"""User queries. No commits: the service decides when a transaction ends."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import locks
from app.modules.users.models import Role, User, UserStatus


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
    db: AsyncSession, *, email: str, handle: str, password_hash: str, role: Role = Role.USER
) -> User | None:
    """Insert a user. None if the email or handle is taken: no exception, no savepoint needed."""
    statement = (
        insert(User)
        .values(email=email, handle=handle, password_hash=password_hash, role=role)
        .on_conflict_do_nothing()
        .returning(User)
    )
    return await db.scalar(statement)


async def get_for_write(db: AsyncSession, user_id: UUID) -> User | None:
    """The user, read after taking their write lock, shared, until the transaction ends.

    A status change takes the same lock exclusively (lock_for_status): it waits for the writes
    under way, and writes that come later queue behind it, then read the new status. An
    advisory lock, not a row lock: new row share locks pass a waiting FOR UPDATE, so a stream
    of writes could hold a ban off for good; advisory locks queue in order.
    """
    await _user_writes_lock(db, user_id, "pg_advisory_xact_lock_shared")
    query = select(User).where(User.id == user_id)
    return await db.scalar(query.execution_options(populate_existing=True))  # not the cached row


async def lock_for_status(db: AsyncSession, user_id: UUID) -> User | None:
    """The user, with their write lock taken exclusively (see get_for_write) and the row
    FOR NO KEY UPDATE: waits for their writes under way, and makes role and status changes run
    one at a time. Not FOR UPDATE: that would wait for foreign key checks of rows that point at
    the user."""
    await _user_writes_lock(db, user_id, "pg_advisory_xact_lock")
    query = select(User).where(User.id == user_id).with_for_update(key_share=True)
    return await db.scalar(query.execution_options(populate_existing=True))


async def _user_writes_lock(db: AsyncSession, user_id: UUID, function: str) -> None:
    # A hash collision only makes two users' writes and bans wait for each other a moment.
    statement = text(f"SELECT {function}(:namespace, hashtext(:user_id))")
    await db.execute(statement, {"namespace": locks.USER_WRITES, "user_id": str(user_id)})


async def get_status(db: AsyncSession, user_id: UUID) -> UserStatus | None:
    """Only the status: a cheap read that leaves no object for the session to track."""
    return await db.scalar(select(User.status).where(User.id == user_id))
