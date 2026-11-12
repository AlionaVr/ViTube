"""DB rules for watch history: they hold whatever the app does."""

from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.history.models import HistoryEntry
from app.modules.users.models import User
from app.modules.videos.models import Video
from tests.videos.factories import make_user, make_video


async def watched(db: AsyncSession, user: User, video: Video, position_sec: int = 0) -> None:
    db.add(HistoryEntry(user_id=user.id, video_id=video.id, position_sec=position_sec))
    await db.commit()


async def rows(db: AsyncSession) -> set[tuple[UUID, UUID]]:
    result = await db.execute(select(HistoryEntry.user_id, HistoryEntry.video_id))
    return {(user_id, video_id) for user_id, video_id in result}


async def test_position_is_never_negative(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")
    db.add(HistoryEntry(user_id=anna.id, video_id=(await make_video(db, anna)).id, position_sec=-1))

    with pytest.raises(IntegrityError, match="ck_watch_history_position_sec_not_negative"):
        await db.commit()


async def test_a_video_is_in_a_users_history_once(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")
    video = await make_video(db, anna)
    await watched(db, anna, video)
    db.add(HistoryEntry(user_id=anna.id, video_id=video.id, position_sec=3))

    with pytest.raises(IntegrityError, match="pk_watch_history"):
        await db.commit()


async def test_deleting_a_user_removes_their_history(
    db: AsyncSession, admin_engine: AsyncEngine
) -> None:
    anna, bob, carl = [await make_user(db, name) for name in ("anna", "bob", "carl")]
    first, second = await make_video(db, anna), await make_video(db, anna)
    for user, video in ((bob, first), (bob, second), (carl, first)):
        await watched(db, user, video)

    # The superuser: no feature deletes users yet.
    async with admin_engine.begin() as conn:
        await conn.execute(delete(User).where(User.id == bob.id))

    assert await rows(db) == {(carl.id, first.id)}


async def test_deleting_a_video_removes_it_from_every_history(
    db: AsyncSession, admin_engine: AsyncEngine
) -> None:
    anna, bob, carl = [await make_user(db, name) for name in ("anna", "bob", "carl")]
    first, second = await make_video(db, anna), await make_video(db, anna)
    for user, video in ((bob, first), (bob, second), (carl, first)):
        await watched(db, user, video)

    # The superuser: no feature deletes videos yet.
    async with admin_engine.begin() as conn:
        await conn.execute(delete(Video).where(Video.id == first.id))

    assert await rows(db) == {(bob.id, second.id)}
