"""Restoring a hidden video, dismissing reports, the hidden list, and no moderating one's own."""

import asyncio

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditAction
from app.modules.moderation import repository as moderation_repository
from app.modules.moderation import service as moderation_service
from app.modules.reports.models import ReportStatus
from app.modules.videos.models import Video
from tests.interactions.conftest import user_by_email
from tests.moderation.conftest import (
    MODERATOR_EMAIL,
    OWNER_EMAIL,
    act,
    audit_entries,
    hide,
    hide_directly,
    report,
    reports_of,
)
from tests.moderation.test_hide import meet_before
from tests.videos.factories import get_video, make_video


async def hidden_ids(client: AsyncClient) -> list[str]:
    """Follow next_cursor to the end."""
    ids: list[str] = []
    cursor = None
    while True:
        params = {"cursor": cursor} if cursor else {}
        response = await client.get("/api/moderation/videos/hidden", params=params)
        assert response.status_code == 200
        ids += [item["id"] for item in response.json()["items"]]
        cursor = response.json()["next_cursor"]
        if cursor is None:
            return ids


# --- Restore ---


async def test_restoring_shows_the_video_again_and_is_logged(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await report(viewer, video)
    await hide(moderator, video)

    assert (await act(moderator, video, "restore")).status_code == 204

    assert not (await get_video(db, video.public_id)).is_hidden
    assert (await viewer.get(f"/api/videos/{video.public_id}")).status_code == 200
    [closed] = await reports_of(db, video)
    assert closed.status is ReportStatus.ACTIONED  # a restore doesn't reopen reports
    entries = await audit_entries(db)
    assert [entry.action for entry in entries] == [
        AuditAction.HIDE_VIDEO,
        AuditAction.RESTORE_VIDEO,
    ]
    assert entries[1].actor_id == (await user_by_email(db, MODERATOR_EMAIL)).id
    assert entries[1].details == {}


async def test_restoring_a_shown_video_changes_and_logs_nothing(
    moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    assert (await act(moderator, video, "restore")).status_code == 204
    assert await audit_entries(db) == []


# --- Dismiss ---


async def test_dismissing_closes_the_reports_and_keeps_the_video(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await report(viewer, video)

    assert (await act(moderator, video, "dismiss")).status_code == 204

    assert not (await get_video(db, video.public_id)).is_hidden
    [closed] = await reports_of(db, video)
    assert closed.status is ReportStatus.DISMISSED
    assert closed.resolved_by == (await user_by_email(db, MODERATOR_EMAIL)).id
    assert (await moderator.get("/api/moderation/reports")).json()["items"] == []
    [entry] = await audit_entries(db)
    assert entry.action is AuditAction.DISMISS_VIDEO
    assert entry.details == {"reports": 1}


async def test_dismissing_with_no_open_reports_logs_nothing(
    moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    assert (await act(moderator, video, "dismiss")).status_code == 204
    assert await audit_entries(db) == []


async def test_a_report_after_a_dismissal_opens_a_new_case(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    await report(viewer, video)
    await act(moderator, video, "dismiss")

    assert (await report(viewer, video, "violent")).status_code == 204

    [case] = (await moderator.get("/api/moderation/reports")).json()["items"]
    assert case["reasons"] == ["violent"]


async def test_hide_and_dismiss_at_once_close_each_report_once(
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await report(viewer, video)
    meet_before(monkeypatch, moderation_repository, "lock_video", 2)

    responses = await asyncio.gather(hide(moderator, video), act(admin, video, "dismiss"))

    assert [response.status_code for response in responses] == [204, 204]
    [closed] = await reports_of(db, video)
    entries = await audit_entries(db)
    # Whoever locked the video first closed the report; the other found none.
    assert sum(entry.details.get("reports", 0) for entry in entries) == 1
    expected = {
        ReportStatus.ACTIONED: AuditAction.HIDE_VIDEO,
        ReportStatus.DISMISSED: AuditAction.DISMISS_VIDEO,
    }[closed.status]
    assert next(e for e in entries if e.details.get("reports")).action is expected
    assert (await get_video(db, video.public_id)).is_hidden  # the hide happened either way


# --- The hidden list ---


async def test_the_hidden_list_has_only_hidden_videos_newest_first(
    moderator: AsyncClient,
    owner: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(moderation_service, "HIDDEN_PAGE_SIZE", 2)
    anna = await user_by_email(db, OWNER_EMAIL)
    videos = [await make_video(db, anna) for _ in range(4)]
    for video in videos[:3]:
        await hide_directly(db, video)

    assert await hidden_ids(moderator) == [video.public_id for video in reversed(videos[:3])]


async def test_only_moderators_list_hidden_videos(
    guest: AsyncClient, viewer: AsyncClient, admin: AsyncClient
) -> None:
    assert (await guest.get("/api/moderation/videos/hidden")).status_code == 401
    assert (await viewer.get("/api/moderation/videos/hidden")).status_code == 403
    assert (await admin.get("/api/moderation/videos/hidden")).status_code == 200


# --- Roles and one's own videos ---


@pytest.mark.parametrize("action", ["restore", "dismiss"])
async def test_only_moderators_restore_and_dismiss(
    guest: AsyncClient, viewer: AsyncClient, db: AsyncSession, video: Video, action: str
) -> None:
    await hide_directly(db, video)

    assert (await act(guest, video, action)).status_code == 401
    assert (await act(viewer, video, action)).status_code == 403
    assert (await get_video(db, video.public_id)).is_hidden


@pytest.mark.parametrize("action", ["hide", "restore", "dismiss"])
async def test_a_moderator_cant_moderate_their_own_video(
    viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, action: str
) -> None:
    own = await make_video(db, await user_by_email(db, MODERATOR_EMAIL))
    await report(viewer, own)
    if action == "restore":
        await hide_directly(db, own)

    response = await (hide(moderator, own) if action == "hide" else act(moderator, own, action))

    assert response.status_code == 403
    [still_open] = await reports_of(db, own)
    assert still_open.status is ReportStatus.OPEN
    assert (await get_video(db, own.public_id)).is_hidden is (action == "restore")
    assert await audit_entries(db) == []


async def test_unknown_videos_are_not_found(moderator: AsyncClient) -> None:
    for action in ("restore", "dismiss"):
        response = await moderator.post(
            f"/api/moderation/videos/AAAAAAAAAAA/{action}",
            headers={"X-CSRF-Token": moderator.cookies["csrf_token"]},
        )
        assert response.status_code == 404
