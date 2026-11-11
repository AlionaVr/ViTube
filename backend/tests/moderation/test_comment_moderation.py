"""Reported comments: reporting, deleting (soft, with counters), dismissing, and races."""

import asyncio
from uuid import UUID

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditAction, TargetType
from app.modules.comments import repository as comments_repository
from app.modules.comments.models import Comment
from app.modules.reports.models import Report, ReportStatus
from app.modules.videos.models import Video
from tests.interactions.conftest import csrf, meet_after, posted, replies_to, user_by_email
from tests.moderation.conftest import (
    MODERATOR_EMAIL,
    OWNER_EMAIL,
    audit_entries,
    hide_directly,
)
from tests.videos.factories import get_video, make_video


async def report_comment(client: AsyncClient, comment_id: object, reason: str = "spam") -> Response:
    return await client.post(
        f"/api/comments/{comment_id}/report",
        json={"reason": reason, "details": "Bot"},
        headers=csrf(client),
    )


async def delete(client: AsyncClient, comment_id: object) -> Response:
    return await client.delete(f"/api/moderation/comments/{comment_id}", headers=csrf(client))


async def dismiss(client: AsyncClient, comment_id: object) -> Response:
    return await client.post(f"/api/moderation/comments/{comment_id}/dismiss", headers=csrf(client))


async def comment_row(db: AsyncSession, comment_id: object) -> Comment:
    query = select(Comment).where(Comment.id == UUID(str(comment_id)))
    comment = await db.scalar(query.execution_options(populate_existing=True))
    assert comment is not None
    return comment


async def reports_of_comment(db: AsyncSession, comment_id: object) -> list[Report]:
    query = select(Report).where(Report.comment_id == UUID(str(comment_id))).order_by(Report.id)
    return list(await db.scalars(query.execution_options(populate_existing=True)))


async def assert_counters_match(db: AsyncSession, video: Video) -> None:
    """The invariants: counters count exactly the comments not deleted."""
    live = select(func.count()).where(Comment.video_id == video.id, ~Comment.is_deleted)
    assert (await get_video(db, video.public_id)).comment_count == await db.scalar(live)
    roots = await db.scalars(
        select(Comment)
        .where(Comment.video_id == video.id, Comment.parent_id.is_(None), ~Comment.is_deleted)
        .execution_options(populate_existing=True)
    )
    for root in roots.all():
        replies = select(func.count()).where(Comment.parent_id == root.id, ~Comment.is_deleted)
        assert root.reply_count == await db.scalar(replies)


# --- Reporting a comment ---


async def test_a_user_reports_a_comment(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession, video: Video
) -> None:
    comment = await posted(owner, video, "Buy followers at example.com")

    assert (await report_comment(viewer, comment["id"])).status_code == 204

    [stored] = await reports_of_comment(db, comment["id"])
    assert stored.video_id is None
    assert stored.status is ReportStatus.OPEN


async def test_reporting_a_comment_is_refused_when_it_cant_be(
    owner: AsyncClient,
    viewer: AsyncClient,
    guest: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
) -> None:
    comment = await posted(owner, video)
    gone = await posted(owner, video, "Gone")
    await delete(moderator, gone["id"])

    assert (await report_comment(guest, comment["id"])).status_code == 401
    assert (await report_comment(owner, comment["id"])).status_code == 400  # their own
    assert (await report_comment(viewer, gone["id"])).status_code == 404
    await hide_directly(db, video)
    assert (await report_comment(viewer, comment["id"])).status_code == 404
    assert await reports_of_comment(db, comment["id"]) == []


async def test_the_queue_shows_a_comment_with_its_video(
    owner: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    root = await posted(owner, video, "First")
    reply = await posted(owner, video, "Spam reply", root["id"])
    await report_comment(viewer, reply["id"], "spam")

    [case] = (await moderator.get("/api/moderation/reports")).json()["items"]

    assert case["video"] is None
    assert case["comment"]["id"] == reply["id"]
    assert case["comment"]["text"] == "Spam reply"
    assert case["comment"]["is_reply"] is True
    assert case["comment"]["is_deleted"] is False
    assert case["comment"]["author"]["handle"] == (await user_by_email(db, OWNER_EMAIL)).handle
    assert case["comment"]["video"]["id"] == video.public_id
    assert case["reasons"] == ["spam"]


# --- Deleting ---


async def test_deleting_a_reply_drops_it_from_lists_and_counters(
    owner: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    root = await posted(owner, video, "Root")
    keep = await posted(viewer, video, "Kind reply", root["id"])
    rude = await posted(viewer, video, "Rude reply", root["id"])
    await report_comment(owner, rude["id"])

    assert (await delete(moderator, rude["id"])).status_code == 204

    assert [item["id"] for item in (await replies_to(owner, root["id"])).json()["items"]] == [
        keep["id"]
    ]
    assert (await comment_row(db, root["id"])).reply_count == 1
    assert (await get_video(db, video.public_id)).comment_count == 2
    await assert_counters_match(db, video)
    [closed] = await reports_of_comment(db, rude["id"])
    assert closed.status is ReportStatus.ACTIONED
    [entry] = await audit_entries(db)
    assert (entry.action, entry.target_type, entry.target_id) == (
        AuditAction.DELETE_COMMENT,
        TargetType.COMMENT,
        UUID(str(rude["id"])),
    )
    assert entry.actor_id == (await user_by_email(db, MODERATOR_EMAIL)).id
    assert entry.details == {"replies": 0, "reports": 1}


async def test_deleting_a_root_deletes_its_thread(
    owner: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    other = await posted(viewer, video, "Another thread")
    root = await posted(owner, video, "Root")
    reply = await posted(viewer, video, "Reply", root["id"])
    await report_comment(viewer, root["id"])
    await report_comment(owner, reply["id"])

    assert (await delete(moderator, root["id"])).status_code == 204

    listed = (await owner.get(f"/api/videos/{video.public_id}/comments")).json()["items"]
    assert [item["id"] for item in listed] == [other["id"]]
    assert (await replies_to(owner, root["id"])).status_code == 404
    assert (await comment_row(db, reply["id"])).is_deleted
    assert (await get_video(db, video.public_id)).comment_count == 1
    await assert_counters_match(db, video)
    for comment_id in (root["id"], reply["id"]):
        [closed] = await reports_of_comment(db, comment_id)
        assert closed.status is ReportStatus.ACTIONED
    [entry] = await audit_entries(db)
    assert entry.details == {"replies": 1, "reports": 2}


async def test_deleting_a_reply_then_its_root_counts_each_once(
    owner: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    root = await posted(owner, video, "Root")
    reply = await posted(viewer, video, "Reply", root["id"])
    await posted(viewer, video, "Another reply", root["id"])

    await delete(moderator, reply["id"])
    await delete(moderator, root["id"])

    assert (await get_video(db, video.public_id)).comment_count == 0
    await assert_counters_match(db, video)


async def test_deleting_again_changes_and_logs_nothing(
    owner: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    comment = await posted(owner, video)
    await delete(moderator, comment["id"])

    assert (await delete(moderator, comment["id"])).status_code == 204

    assert (await get_video(db, video.public_id)).comment_count == 0
    assert len(await audit_entries(db)) == 1


async def test_a_deleted_comment_takes_no_ratings_or_replies(
    owner: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, video: Video
) -> None:
    root = await posted(owner, video, "Root")
    reply = await posted(viewer, video, "Reply", root["id"])
    await delete(moderator, reply["id"])

    response = await viewer.put(
        f"/api/comments/{reply['id']}/rating", json={"rating": "like"}, headers=csrf(viewer)
    )
    assert response.status_code == 404
    # Replying to a deleted reply: refused, though its thread lives on.
    body = {"text": "Hi", "parent_id": reply["id"]}
    path = f"/api/videos/{video.public_id}/comments"
    assert (await viewer.post(path, json=body, headers=csrf(viewer))).status_code == 404
    await delete(moderator, root["id"])
    body = {"text": "Hi", "parent_id": root["id"]}
    assert (await viewer.post(path, json=body, headers=csrf(viewer))).status_code == 404


# --- Dismissing, roles, one's own ---


async def test_dismissing_closes_a_comments_reports(
    owner: AsyncClient, viewer: AsyncClient, moderator: AsyncClient, db: AsyncSession, video: Video
) -> None:
    comment = await posted(owner, video)
    await report_comment(viewer, comment["id"])

    assert (await dismiss(moderator, comment["id"])).status_code == 204
    assert (await dismiss(moderator, comment["id"])).status_code == 204  # nothing left: no entry

    assert not (await comment_row(db, comment["id"])).is_deleted
    [closed] = await reports_of_comment(db, comment["id"])
    assert closed.status is ReportStatus.DISMISSED
    [entry] = await audit_entries(db)
    assert (entry.action, entry.details) == (AuditAction.DISMISS_COMMENT, {"reports": 1})


async def test_only_moderators_delete_or_dismiss_comments(
    owner: AsyncClient, viewer: AsyncClient, guest: AsyncClient, db: AsyncSession, video: Video
) -> None:
    comment = await posted(owner, video)

    for client, expected in ((guest, 401), (viewer, 403)):
        assert (await delete(client, comment["id"])).status_code == expected
        assert (await dismiss(client, comment["id"])).status_code == expected
    assert not (await comment_row(db, comment["id"])).is_deleted


async def test_a_moderator_cant_moderate_their_own_comment(
    moderator: AsyncClient, viewer: AsyncClient, db: AsyncSession, video: Video
) -> None:
    own = await posted(moderator, video, "Mine")
    await report_comment(viewer, own["id"])

    assert (await delete(moderator, own["id"])).status_code == 403
    assert (await dismiss(moderator, own["id"])).status_code == 403
    assert not (await comment_row(db, own["id"])).is_deleted
    assert await audit_entries(db) == []


async def test_unknown_comments_are_not_found(moderator: AsyncClient) -> None:
    unknown = "0193a5c2-0000-7000-8000-000000000000"
    assert (await delete(moderator, unknown)).status_code == 404
    assert (await dismiss(moderator, unknown)).status_code == 404


# --- Races: the thread root's lock keeps counters exact ---


async def test_a_reply_racing_its_roots_delete_keeps_counters_right(
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meet_after(monkeypatch, comments_repository, "get", 2)
    for round_ in range(4):  # either may lock the root first; each run checks the outcome
        root = await posted(owner, video, f"Root {round_}")
        body = {"text": "Late reply", "parent_id": root["id"]}
        reply, deleted = await asyncio.gather(
            viewer.post(f"/api/videos/{video.public_id}/comments", json=body, headers=csrf(viewer)),
            delete(moderator, root["id"]),
        )

        assert deleted.status_code == 204
        assert reply.status_code in (201, 404)  # before the delete, or refused after it
        if reply.status_code == 201:
            assert (await comment_row(db, reply.json()["id"])).is_deleted  # went with its thread
        await assert_counters_match(db, video)
    assert (await get_video(db, video.public_id)).comment_count == 0


async def test_deleting_a_reply_and_its_root_at_once_counts_each_once(
    owner: AsyncClient,
    viewer: AsyncClient,
    moderator: AsyncClient,
    admin: AsyncClient,
    db: AsyncSession,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keep = await posted(viewer, video, "Another thread")
    root = await posted(owner, video, "Root")
    reply = await posted(viewer, video, "Reply", root["id"])
    meet_after(monkeypatch, comments_repository, "get", 2)

    responses = await asyncio.gather(delete(moderator, reply["id"]), delete(admin, root["id"]))

    assert [response.status_code for response in responses] == [204, 204]
    assert (await get_video(db, video.public_id)).comment_count == 1
    assert not (await comment_row(db, keep["id"])).is_deleted
    await assert_counters_match(db, video)


async def test_a_video_with_no_comments_left_stays_at_zero(
    owner: AsyncClient, moderator: AsyncClient, db: AsyncSession
) -> None:
    video = await make_video(db, await user_by_email(db, OWNER_EMAIL))
    comment = await posted(owner, video)
    await delete(moderator, comment["id"])

    assert (await get_video(db, video.public_id)).comment_count == 0
