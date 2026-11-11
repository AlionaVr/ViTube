"""Moderator actions (ADR 0009). The service commits, like @Transactional.

Each action is one transaction: lock the target, change it, close its open reports, write the
audit entry, commit. So the log never lacks an action or holds one that didn't happen.
"""

import logging
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.core.pagination import Page, decode_cursor, split_page
from app.modules.audit import repository as audit
from app.modules.audit.models import AuditAction, TargetType
from app.modules.audit.repository import Actor
from app.modules.auth.sessions import SessionStore
from app.modules.comments import repository as comments_repository
from app.modules.comments.models import Comment
from app.modules.moderation import repository as moderation
from app.modules.moderation.schemas import (
    ModeratedComment,
    ModeratedVideo,
    ReportCase,
    RestrictedAccount,
)
from app.modules.reports import repository as reports
from app.modules.reports.models import ReportReason, ReportStatus
from app.modules.users import repository as users
from app.modules.users.models import Role, User, UserStatus
from app.modules.videos.models import Video

log = logging.getLogger(__name__)

QUEUE_PAGE_SIZE = 20
HIDDEN_PAGE_SIZE = 20
ACCOUNTS_PAGE_SIZE = 20


async def list_cases(db: AsyncSession, cursor: str | None) -> Page[ReportCase]:
    after = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    cases = await reports.list_open_cases(db, after=after, limit=QUEUE_PAGE_SIZE + 1)
    page, next_cursor = split_page(cases, QUEUE_PAGE_SIZE, lambda case: (case.first_id,))
    comments = await moderation.comments_with_authors(
        db, [case.comment_id for case in page if case.comment_id]
    )
    video_ids = {case.video_id for case in page if case.video_id}
    video_ids |= {comment.video_id for comment, _ in comments.values()}
    videos = {
        video_id: ModeratedVideo.of(video, owner)
        for video_id, (video, owner) in (await moderation.videos_with_owners(db, video_ids)).items()
    }
    items = []
    for case in page:
        # A row deleted meanwhile took its reports with it: skip its case.
        if case.video_id and (video := videos.get(case.video_id)):
            items.append(ReportCase.of(case, video=video))
        elif case.comment_id and (found := comments.get(case.comment_id)):
            comment, author = found
            moderated = ModeratedComment.of(comment, author, videos[comment.video_id])
            items.append(ReportCase.of(case, comment=moderated))
    return Page(items=items, next_cursor=next_cursor)


async def list_hidden(db: AsyncSession, cursor: str | None) -> Page[ModeratedVideo]:
    before = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    rows = await moderation.list_hidden(db, before=before, limit=HIDDEN_PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, HIDDEN_PAGE_SIZE, lambda row: (row[0].id,))
    items = [ModeratedVideo.of(video, owner) for video, owner in page]
    return Page(items=items, next_cursor=next_cursor)


async def list_restricted(
    db: AsyncSession, status: UserStatus | None, cursor: str | None
) -> Page[RestrictedAccount]:
    before = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    rows = await moderation.list_restricted(
        db, status=status, before=before, limit=ACCOUNTS_PAGE_SIZE + 1
    )
    page, next_cursor = split_page(rows, ACCOUNTS_PAGE_SIZE, lambda user: (user.id,))
    return Page(items=[RestrictedAccount.of(user) for user in page], next_cursor=next_cursor)


async def set_status(
    db: AsyncSession,
    sessions: SessionStore,
    actor: Actor,
    user_id: UUID,
    status: UserStatus,
    reason: str = "",
) -> None:
    """Ban, terminate or reinstate an account (admins and the CLI).

    The lock FOR UPDATE waits for the user's writes under way (they hold KEY SHARE, see
    auth.deps.optional_user), so none of them commits after the ban. The ban is in force once
    this commits: every request reads the status from the DB. Ending the sessions after that
    only cleans up, so a Redis failure is logged, not an error.
    """
    user = await users.lock_for_status(db, user_id)
    if user is None:
        raise NotFound("No such user")
    if user.id == actor.user_id:
        raise Forbidden("You can't change your own account's status")
    if user.role is Role.ADMIN:  # read under the lock: a role change can't slip in
        raise Forbidden("An admin's account can't be restricted: change their role first")
    previous = user.status
    if previous is not status:
        user.status = status
        details = {"from": previous, "to": status} | ({"reason": reason} if reason else {})
        await audit.record(
            db, actor, AuditAction.SET_USER_STATUS, TargetType.USER, user.id, **details
        )
    await db.commit()
    if status is not UserStatus.ACTIVE:  # again on a repeat: a retry finishes a failed revoke
        try:
            await sessions.revoke_all(user.id)
        except RedisError:
            log.exception("Could not end the sessions of user %s; requests refuse them", user.id)


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


async def delete_comment(db: AsyncSession, moderator: User, comment_id: UUID) -> None:
    """Delete the comment, and the replies of a thread's root; close their open reports.

    Locks the thread's root first, as a new reply does: a reply either lands before the delete
    and is deleted with the thread, or waits and finds the root deleted. Counters drop by exactly
    what was deleted here, so two deletes at once never take a comment off twice.
    """
    comment = await _comment(db, moderator, comment_id)
    root_id = comment.parent_id or comment.id
    await moderation.lock_thread(db, root_id)
    deleted = []
    if await moderation.mark_deleted(db, comment.id):
        deleted.append(comment.id)
        if comment.parent_id is None:
            deleted += await moderation.mark_replies_deleted(db, comment.id)
        else:
            await moderation.remove_reply(db, comment.parent_id)
        await moderation.remove_comments(db, comment.video_id, len(deleted))
    closed = await reports.resolve_open_of_comments(
        db, deleted or [comment.id], status=ReportStatus.ACTIONED, resolved_by=moderator.id
    )
    if deleted or closed:
        await audit.record(
            db,
            Actor.of(moderator),
            AuditAction.DELETE_COMMENT,
            TargetType.COMMENT,
            comment.id,
            replies=max(len(deleted) - 1, 0),
            reports=closed,
        )
    await db.commit()


async def dismiss_comment(db: AsyncSession, moderator: User, comment_id: UUID) -> None:
    """Close the comment's open reports: nothing wrong with it."""
    comment = await _comment(db, moderator, comment_id)
    await moderation.lock_thread(db, comment.parent_id or comment.id)  # same order as a delete
    closed = await reports.resolve_open_of_comments(
        db, [comment.id], status=ReportStatus.DISMISSED, resolved_by=moderator.id
    )
    if closed:
        await audit.record(
            db,
            Actor.of(moderator),
            AuditAction.DISMISS_COMMENT,
            TargetType.COMMENT,
            comment.id,
            reports=closed,
        )
    await db.commit()


async def _comment(db: AsyncSession, moderator: User, comment_id: UUID) -> Comment:
    comment = await comments_repository.get(db, comment_id)
    if comment is None:
        raise NotFound("Comment not found")
    if comment.author_id == moderator.id:
        raise Forbidden("Another moderator decides about your own comment")
    return comment


async def _lock_video(db: AsyncSession, moderator: User, public_id: str) -> Video:
    """The video, locked first: actions on one video run one at a time, then touch its reports."""
    video = await moderation.lock_video(db, public_id)
    if video is None:
        raise NotFound("Video not found")
    if video.owner_id == moderator.id:
        raise Forbidden("Another moderator decides about your own video")
    return video
