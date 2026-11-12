"""Reporting a video (ADR 0009): who may, what is stored, and the limits."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.models import ReportReason, ReportStatus
from app.modules.reports.service import REPORTS_PER_USER
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.interactions.conftest import user_by_email
from tests.moderation.conftest import OWNER_EMAIL, VIEWER_EMAIL, report, reports_of
from tests.videos.factories import make_video


async def test_a_user_reports_a_video(viewer: AsyncClient, db: AsyncSession, video: Video) -> None:
    response = await report(viewer, video, "harassment", "  Mocks a classmate  ")

    assert response.status_code == 204
    [stored] = await reports_of(db, video)
    assert stored.reporter_id == (await user_by_email(db, VIEWER_EMAIL)).id
    assert stored.reason is ReportReason.HARASSMENT
    assert stored.details == "Mocks a classmate"
    assert stored.status is ReportStatus.OPEN
    assert stored.resolved_at is None


async def test_reporting_again_while_open_changes_nothing(
    viewer: AsyncClient, db: AsyncSession, video: Video
) -> None:
    assert (await report(viewer, video, "spam")).status_code == 204
    assert (await report(viewer, video, "violent", "again")).status_code == 204

    [stored] = await reports_of(db, video)
    assert stored.reason is ReportReason.SPAM


async def test_a_guest_must_sign_in(guest: AsyncClient, video: Video) -> None:
    assert (await report(guest, video)).status_code == 401


async def test_the_owner_cant_report_their_own_video(
    owner: AsyncClient, db: AsyncSession, video: Video
) -> None:
    response = await report(owner, video)

    assert response.status_code == 400
    assert await reports_of(db, video) == []


@pytest.mark.parametrize(
    ("visibility", "status"),
    [(Visibility.PRIVATE, VideoStatus.READY), (Visibility.PUBLIC, VideoStatus.PROCESSING)],
)
async def test_a_video_the_user_cant_watch_is_not_found(
    viewer: AsyncClient,
    db: AsyncSession,
    owner: AsyncClient,
    visibility: Visibility,
    status: VideoStatus,
) -> None:
    video = await make_video(
        db, await user_by_email(db, OWNER_EMAIL), visibility=visibility, status=status
    )

    assert (await report(viewer, video)).status_code == 404
    assert await reports_of(db, video) == []


@pytest.mark.parametrize(
    "body",
    [
        {"reason": "boring"},
        {},
        {"reason": "spam", "details": "x" * 501},
        {"reason": "spam", "details": "null\x00byte"},
    ],
    ids=["unknown reason", "no reason", "details too long", "control character"],
)
async def test_invalid_reports_are_refused(
    viewer: AsyncClient, db: AsyncSession, video: Video, body: dict[str, str]
) -> None:
    response = await viewer.post(
        f"/api/videos/{video.public_id}/report",
        json=body,
        headers={"X-CSRF-Token": viewer.cookies["csrf_token"]},
    )

    assert response.status_code == 422
    assert await reports_of(db, video) == []


async def test_reports_are_limited_per_account(
    viewer: AsyncClient, db: AsyncSession, video: Video
) -> None:
    for _ in range(REPORTS_PER_USER.limit):
        assert (await report(viewer, video)).status_code == 204

    response = await report(viewer, video)

    assert response.status_code == 429
    assert "Retry-After" in response.headers
