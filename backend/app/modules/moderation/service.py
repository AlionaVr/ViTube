"""Moderator actions (ADR 0009). The service commits, like @Transactional.

Each action is one transaction: lock the target, change it, close its open reports, write the
audit entry, commit. So the log never lacks an action or holds one that didn't happen.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.core.pagination import Page, decode_cursor, split_page
from app.modules.audit import repository as audit
from app.modules.audit.models import AuditAction, TargetType
from app.modules.audit.repository import Actor
from app.modules.moderation import repository as moderation
from app.modules.moderation.schemas import ModeratedVideo, ReportCase
from app.modules.reports import repository as reports
from app.modules.reports.models import ReportReason, ReportStatus
from app.modules.users.models import User
from app.modules.videos.models import Video

QUEUE_PAGE_SIZE = 20
HIDDEN_PAGE_SIZE = 20


async def list_cases(db: AsyncSession, cursor: str | None) -> Page[ReportCase]:
    after = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    cases = await reports.list_open_cases(db, after=after, limit=QUEUE_PAGE_SIZE + 1)
    page, next_cursor = split_page(cases, QUEUE_PAGE_SIZE, lambda case: (case.first_id,))
    video_ids = [case.video_id for case in page if case.video_id]
    videos = await moderation.videos_with_owners(db, video_ids)
    items = [
        ReportCase.of(case, ModeratedVideo.of(*found))
        for case in page
        # A video deleted meanwhile took its reports with it.
        if case.video_id and (found := videos.get(case.video_id))
    ]
    return Page(items=items, next_cursor=next_cursor)


async def list_hidden(db: AsyncSession, cursor: str | None) -> Page[ModeratedVideo]:
    before = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    rows = await moderation.list_hidden(db, before=before, limit=HIDDEN_PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, HIDDEN_PAGE_SIZE, lambda row: (row[0].id,))
    items = [ModeratedVideo.of(video, owner) for video, owner in page]
    return Page(items=items, next_cursor=next_cursor)


async def hide_video(
    db: AsyncSession, moderator: User, public_id: str, reason: ReportReason
) -> None:
    """Hide the video and close its open reports. Hiding a hidden video only closes reports."""
    video = await _lock_video(db, moderator, public_id)
    hidden_now = not video.is_hidden
    video.is_hidden = True
    closed = await reports.resolve_open_of_video(
        db, video.id, status=ReportStatus.ACTIONED, resolved_by=moderator.id
    )
    if hidden_now or closed:  # nothing changed: nothing to log
        await audit.record(
            db,
            Actor.of(moderator),
            AuditAction.HIDE_VIDEO,
            TargetType.VIDEO,
            video.id,
            reason=reason,
            reports=closed,
        )
    await db.commit()


async def restore_video(db: AsyncSession, moderator: User, public_id: str) -> None:
    """Show the video again. Its closed reports stay closed."""
    video = await _lock_video(db, moderator, public_id)
    if video.is_hidden:
        video.is_hidden = False
        await audit.record(
            db, Actor.of(moderator), AuditAction.RESTORE_VIDEO, TargetType.VIDEO, video.id
        )
    await db.commit()


async def dismiss_video(db: AsyncSession, moderator: User, public_id: str) -> None:
    """Close the video's open reports: nothing wrong with it."""
    video = await _lock_video(db, moderator, public_id)
    closed = await reports.resolve_open_of_video(
        db, video.id, status=ReportStatus.DISMISSED, resolved_by=moderator.id
    )
    if closed:
        await audit.record(
            db,
            Actor.of(moderator),
            AuditAction.DISMISS_VIDEO,
            TargetType.VIDEO,
            video.id,
            reports=closed,
        )
    await db.commit()


async def _lock_video(db: AsyncSession, moderator: User, public_id: str) -> Video:
    """The video, locked first: actions on one video run one at a time, then touch its reports."""
    video = await moderation.lock_video(db, public_id)
    if video is None:
        raise NotFound("Video not found")
    if video.owner_id == moderator.id:
        raise Forbidden("Another moderator decides about your own video")
    return video
