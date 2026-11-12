"""A write that passed the "not hidden" check just before a hide commits (ADR 0009): it is refused
as a whole, rows and counters alike, and a report waits for the hide or the hide for it, with
no deadlock either way."""

import asyncio

import pytest
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments import repository as comments_repository
from app.modules.comments.models import Comment
from app.modules.reactions import repository as reactions_repository
from app.modules.reactions.models import VideoReaction
from app.modules.reports import repository as reports_repository
from app.modules.reports.models import ReportStatus
from app.modules.videos.models import Video
from app.modules.views import repository as views_repository
from tests.interactions.conftest import csrf, post, posted
from tests.interactions.test_views_api import WAIT, Clock, clock, finish, start  # noqa: F401
from tests.moderation.conftest import hide, hold, report, reports_of
from tests.videos.factories import get_video


async def count(db: AsyncSession, model: type, **where: object) -> int:
    query = select(func.count()).select_from(model).filter_by(**where)
    return await db.scalar(query.execution_options(populate_existing=True)) or 0


async def test_a_comment_checked_before_a_hide_is_refused(
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = hold(monkeypatch, comments_repository, "add_comment")
    posting = asyncio.create_task(post(viewer, video, "Just in time"))
    await entered.wait()  # past get_ready: the video wasn't hidden then

    assert (await hide(moderator, video)).status_code == 204
    release.set()

    assert (await posting).status_code == 404
    assert await count(db, Comment, video_id=video.id) == 0
    assert (await get_video(db, video.public_id)).comment_count == 0


async def test_a_reply_racing_a_hide_rolls_back_its_thread_count(
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = await posted(owner, video, "Thread")
    entered, release = hold(monkeypatch, comments_repository, "add_comment")
    replying = asyncio.create_task(post(viewer, video, "Reply", parent_id=root["id"]))
    await entered.wait()  # the thread's reply count went up in this transaction already

    assert (await hide(moderator, video)).status_code == 204
    release.set()

    assert (await replying).status_code == 404
    thread = await db.get(Comment, root["id"], populate_existing=True)
    assert thread is not None and thread.reply_count == 0
    assert await count(db, Comment, video_id=video.id) == 1
    assert (await get_video(db, video.public_id)).comment_count == 1


@pytest.mark.parametrize("rating", ["like", "dislike"])  # a dislike moves no like count
async def test_a_rating_racing_a_hide_rolls_back(
    rating: str,
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = hold(monkeypatch, reactions_repository, "add_likes")
    path = f"/api/videos/{video.public_id}/rating"
    rating_it = asyncio.create_task(viewer.put(path, json={"rating": rating}, headers=csrf(viewer)))
    await entered.wait()  # the reaction row is written in this transaction already

    assert (await hide(moderator, video)).status_code == 204
    release.set()

    assert (await rating_it).status_code == 404
    assert await count(db, VideoReaction, target_id=video.id) == 0
    assert (await get_video(db, video.public_id)).like_count == 0


async def test_a_view_racing_a_hide_is_not_counted(
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    clock: Clock,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (await start(viewer, video)).status_code == 204
    clock.advance(WAIT)
    entered, release = hold(monkeypatch, views_repository, "add_view")
    finishing = asyncio.create_task(finish(viewer, video))
    await entered.wait()

    assert (await hide(moderator, video)).status_code == 204
    release.set()

    assert (await finishing).status_code == 404
    assert (await get_video(db, video.public_id)).view_count == 0


async def test_a_report_after_a_hide_began_is_refused(
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = hold(monkeypatch, reports_repository, "lock_open_video")
    reporting = asyncio.create_task(report(viewer, video))
    await entered.wait()  # past get_ready

    assert (await hide(moderator, video)).status_code == 204
    release.set()

    assert (await reporting).status_code == 404
    assert await reports_of(db, video) == []  # no open case on a hidden video


async def test_a_hide_waits_for_a_report_under_way_and_closes_it(
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = hold(monkeypatch, reports_repository, "add")
    reporting = asyncio.create_task(report(viewer, video))
    await entered.wait()  # the report holds the video FOR SHARE
    hiding = asyncio.create_task(hide(moderator, video))
    await asyncio.sleep(0.3)
    assert not hiding.done()  # the hide waits for the report...
    release.set()

    async with asyncio.timeout(5):  # ...and neither waits for the other: no deadlock
        assert (await reporting).status_code == 204
        assert (await hiding).status_code == 204
    [closed] = await reports_of(db, video)
    assert closed.status is ReportStatus.ACTIONED


async def test_a_comment_delete_waits_for_a_report_under_way_and_closes_it(
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comment = await posted(owner, video, "Rude")
    entered, release = hold(monkeypatch, reports_repository, "add")
    reporting = asyncio.create_task(
        viewer.post(
            f"/api/comments/{comment['id']}/report", json={"reason": "spam"}, headers=csrf(viewer)
        )
    )
    await entered.wait()  # the report holds the comment and its video FOR SHARE
    path = f"/api/moderation/comments/{comment['id']}"
    deleting = asyncio.create_task(moderator.delete(path, headers=csrf(moderator)))
    await asyncio.sleep(0.3)
    assert not deleting.done()
    release.set()

    async with asyncio.timeout(5):
        assert (await reporting).status_code == 204
        assert (await deleting).status_code == 204
    open_reports = await reports_repository.list_open_cases(db, after=None, limit=10)
    assert open_reports == []
