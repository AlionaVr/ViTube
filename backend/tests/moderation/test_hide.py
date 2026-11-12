"""The report queue and hiding a video (ADR 0009): roles, visibility, the audit log."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import repository as audit_repository
from app.modules.audit.models import AuditAction, AuditSource, TargetType
from app.modules.moderation import repository as moderation_repository
from app.modules.moderation import service as moderation_service
from app.modules.reports import repository as reports_repository
from app.modules.reports.models import ReportReason, ReportStatus
from app.modules.videos.models import Video
from tests.interactions.conftest import browser, signup, user_by_email
from tests.moderation.conftest import (
    MODERATOR_EMAIL,
    OWNER_EMAIL,
    as_dict,
    audit_entries,
    hide,
    report,
    reports_of,
)
from tests.videos.factories import get_video, make_video


async def queue(client: AsyncClient, cursor: str | None = None):
    params = {"cursor": cursor} if cursor else {}
    return await client.get("/api/moderation/reports", params=params)


async def media_auth(client: AsyncClient, video: Video) -> int:
    headers = {"X-Original-URI": f"/media/{video.media_key}"}
    return (await client.get("/internal/media-auth", headers=headers)).status_code


# --- Who may moderate ---


async def test_only_moderators_see_the_queue_and_hide(
    guest: AsyncClient, viewer: AsyncClient, db: AsyncSession, video: Video
) -> None:
    for client, expected in ((guest, 401), (viewer, 403)):
        assert (await queue(client)).status_code == expected
        assert (await hide(client, video)).status_code == expected
    assert not (await get_video(db, video.public_id)).is_hidden


async def test_admins_moderate_too(admin: AsyncClient, db: AsyncSession, video: Video) -> None:
    assert (await queue(admin)).status_code == 200
    assert (await hide(admin, video)).status_code == 204
    assert (await get_video(db, video.public_id)).is_hidden


# --- The queue ---


async def test_reports_of_one_video_make_one_case(
    app: FastAPI, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await report(viewer, video, "spam", "Links to a scam")
    async with browser(app, "10.0.0.9") as other:
        await signup(other, "other@example.com")
        await report(other, video, "harassment", "")
    await report(moderator, video, "spam", "Same scam again")

    response = await queue(moderator)

    assert response.status_code == 200
    [case] = response.json()["items"]
    assert case["video"]["id"] == video.public_id
    assert case["video"]["is_hidden"] is False
    assert case["video"]["channel"]["handle"] == (await user_by_email(db, OWNER_EMAIL)).handle
    assert case["report_count"] == 3
    assert sorted(case["reasons"]) == ["harassment", "spam"]
    assert case["notes"] == ["Same scam again", "Links to a scam"]  # newest first, no blanks


async def test_the_oldest_case_comes_first_and_pages_go_on(
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    owner: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(moderation_service, "QUEUE_PAGE_SIZE", 2)
    anna = await user_by_email(db, OWNER_EMAIL)
    videos = [await make_video(db, anna) for _ in range(3)]
    for video in (videos[1], videos[0], videos[2]):
        await report(viewer, video)
    await report(moderator, videos[1])  # a newer report doesn't move its case

    first = (await queue(moderator)).json()
    second = (await queue(moderator, first["next_cursor"])).json()

    assert [case["video"]["id"] for case in first["items"]] == [
        videos[1].public_id,
        videos[0].public_id,
    ]
    assert [case["video"]["id"] for case in second["items"]] == [videos[2].public_id]
    assert second["next_cursor"] is None


async def test_a_bad_cursor_is_refused(moderator: AsyncClient) -> None:
    assert (await queue(moderator, "not-a-cursor")).status_code == 400


# --- Hiding ---


async def test_hiding_closes_the_reports_and_is_logged(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await report(viewer, video, "violent")

    response = await hide(moderator, video, "violent")

    assert response.status_code == 204
    assert (await get_video(db, video.public_id)).is_hidden
    mod = await user_by_email(db, MODERATOR_EMAIL)
    [closed] = await reports_of(db, video)
    assert closed.status is ReportStatus.ACTIONED
    assert closed.resolved_by == mod.id
    assert closed.resolved_at is not None
    assert (await queue(moderator)).json()["items"] == []
    [entry] = await audit_entries(db)
    assert as_dict(entry) == {
        "source": AuditSource.API,
        "actor_id": mod.id,
        "action": AuditAction.HIDE_VIDEO,
        "target_type": TargetType.VIDEO,
        "target_id": video.id,
        "details": {"reason": "violent", "reports": 1},
    }


async def test_a_hidden_video_is_gone_for_everyone_but_its_owner_and_moderators(
    owner: AsyncClient,
    viewer: AsyncClient,
    guest: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    await hide(moderator, video)

    for outsider in (viewer, guest):
        assert (await outsider.get(f"/api/videos/{video.public_id}")).status_code == 404
    assert await media_auth(viewer, video) == 403  # nginx shows 404
    assert await media_auth(guest, video) == 401
    for insider in (owner, moderator):
        response = await insider.get(f"/api/videos/{video.public_id}")
        assert response.status_code == 200
        assert response.json()["is_hidden"] is True
        assert await media_auth(insider, video) == 200


async def test_hiding_again_changes_and_logs_nothing(
    moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await hide(moderator, video)

    assert (await hide(moderator, video)).status_code == 204
    assert len(await audit_entries(db)) == 1


async def test_hiding_again_closes_a_report_that_came_in_meanwhile(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await hide(moderator, video)
    # A report that passed its checks just before the hide committed.
    viewer_id = (await user_by_email(db, "viewer@example.com")).id
    await reports_repository.add(
        db, reporter_id=viewer_id, video_id=video.id, reason=ReportReason.SPAM, details=""
    )
    await db.commit()

    assert (await hide(moderator, video)).status_code == 204

    [closed] = await reports_of(db, video)
    assert closed.status is ReportStatus.ACTIONED
    second = (await audit_entries(db))[1]
    assert second.details == {"reason": "spam", "reports": 1}


async def test_hiding_an_unknown_video_is_not_found(moderator: AsyncClient) -> None:
    response = await moderator.post(
        "/api/moderation/videos/AAAAAAAAAAA/hide",
        json={"reason": "spam"},
        headers={"X-CSRF-Token": moderator.cookies["csrf_token"]},
    )

    assert response.status_code == 404


async def test_hiding_needs_a_known_reason(moderator: AsyncClient, video: Video) -> None:
    assert (await hide(moderator, video, "boring")).status_code == 422


# --- One transaction: the action and its log entry ---


async def test_no_log_entry_means_no_hide(
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await report(viewer, video)

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit log unavailable")

    monkeypatch.setattr(audit_repository, "record", broken)
    with pytest.raises(RuntimeError):
        await hide(moderator, video)

    assert not (await get_video(db, video.public_id)).is_hidden
    [still_open] = await reports_of(db, video)
    assert still_open.status is ReportStatus.OPEN
    assert await audit_entries(db) == []


def meet_before(monkeypatch: pytest.MonkeyPatch, module: Any, name: str, parties: int) -> None:
    """Parallel requests wait for each other right before `module.name`, then go on together."""
    original: Callable[..., Awaitable[Any]] = getattr(module, name)
    barrier = asyncio.Barrier(parties)

    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        async with asyncio.timeout(10):  # a request that never comes fails the test, not hangs it
            await barrier.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(module, name, wrapped)


async def test_parallel_hides_are_logged_once(
    app: FastAPI,
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await report(viewer, video)
    meet_before(monkeypatch, moderation_repository, "lock_video", 2)

    responses = await asyncio.gather(hide(moderator, video), hide(admin, video))

    assert [response.status_code for response in responses] == [204, 204]
    [entry] = await audit_entries(db)
    assert entry.details["reports"] == 1
