"""Queries of moderator actions. No commits: the service decides when a transaction ends."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.audit.models import AuditAction, AuditEntry, AuditSource, TargetType
from app.modules.comments.models import Comment
from app.modules.users.models import User, UserStatus
from app.modules.videos.models import Video
from app.modules.videos.repository import VideoRow


async def lock_video(db: AsyncSession, public_id: str) -> Video | None:
    """The video, locked until the transaction ends: actions on it run one at a time.

    FOR NO KEY UPDATE: inserts that reference the video (reports, ratings) don't wait for it.
    """
    query = (
        select(Video)
        .where(Video.public_id == public_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)  # the row as locked, not as cached
    )
    return await db.scalar(query)


async def list_hidden(db: AsyncSession, *, before: UUID | None, limit: int) -> Sequence[VideoRow]:
    """Hidden videos, newest first (ids are uuidv7), after the cursor."""
    query = select(Video, User).join(User, User.id == Video.owner_id).where(Video.is_hidden)
    if before is not None:
        query = query.where(Video.id < before)
    return (await db.execute(query.order_by(Video.id.desc()).limit(limit))).all()


async def videos_with_owners(
    db: AsyncSession, video_ids: Collection[UUID]
) -> dict[UUID, tuple[Video, User]]:
    rows = await db.execute(
        select(Video, User).join(User, User.id == Video.owner_id).where(Video.id.in_(video_ids))
    )
    return {video.id: (video, owner) for video, owner in rows}


async def comments_with_authors(
    db: AsyncSession, comment_ids: Collection[UUID]
) -> dict[UUID, tuple[Comment, User]]:
    rows = await db.execute(
        select(Comment, User)
        .join(User, User.id == Comment.author_id)
        .where(Comment.id.in_(comment_ids))
    )
    return {comment.id: (comment, author) for comment, author in rows}


async def lock_thread(db: AsyncSession, root_id: UUID) -> None:
    """Lock a thread's root until the transaction ends. Everyone who writes to a thread (replies,
    deletions) locks its root first, so they run one at a time. FOR NO KEY UPDATE: ratings and
    reports, which only reference it, don't wait."""
    await db.execute(
        select(Comment.id).where(Comment.id == root_id).with_for_update(key_share=True)
    )


async def mark_deleted(db: AsyncSession, comment_id: UUID) -> bool:
    """False if it was deleted already."""
    statement = (
        update(Comment)
        .where(Comment.id == comment_id, ~Comment.is_deleted)
        .values(is_deleted=True)
        .returning(Comment.id)
    )
    return await db.scalar(statement) is not None


async def mark_replies_deleted(db: AsyncSession, root_id: UUID) -> list[UUID]:
    """The thread's replies not deleted yet, now deleted."""
    statement = (
        update(Comment)
        .where(Comment.parent_id == root_id, ~Comment.is_deleted)
        .values(is_deleted=True)
        .returning(Comment.id)
    )
    return list(await db.scalars(statement))


async def remove_reply(db: AsyncSession, root_id: UUID) -> None:
    await db.execute(
        update(Comment).where(Comment.id == root_id).values(reply_count=Comment.reply_count - 1)
    )


async def remove_comments(db: AsyncSession, video_id: UUID, count: int) -> None:
    await db.execute(
        update(Video).where(Video.id == video_id).values(comment_count=Video.comment_count - count)
    )


async def list_restricted(
    db: AsyncSession, *, status: UserStatus | None, before: UUID | None, limit: int
) -> Sequence[User]:
    """Banned and terminated accounts (or one of the two), newest accounts first."""
    query = select(User).where(User.status != UserStatus.ACTIVE)
    if status is not None:
        query = query.where(User.status == status)
    if before is not None:
        query = query.where(User.id < before)
    return (await db.scalars(query.order_by(User.id.desc()).limit(limit))).all()


@dataclass(frozen=True)
class AuditFilter:
    """What the admin narrowed the log to. Each part has its own index."""

    actions: Collection[AuditAction] = ()
    source: AuditSource | None = None
    actor_id: UUID | None = None
    account_id: UUID | None = None  # the account itself, its videos and its comments


async def list_audit(
    db: AsyncSession, filters: AuditFilter, *, before: UUID | None, limit: int
) -> Sequence[AuditEntry]:
    """Newest first (ids are uuidv7), after the cursor."""
    query = select(AuditEntry)
    if filters.actions:
        query = query.where(AuditEntry.action.in_(filters.actions))
    if filters.source is not None:
        query = query.where(AuditEntry.source == filters.source)
    if filters.actor_id is not None:
        query = query.where(AuditEntry.actor_id == filters.actor_id)
    if (account := filters.account_id) is None:
        return (await db.scalars(_newest(query, before, limit))).all()
    # One branch per kind of target, each on ix_audit_log_target_type_target_id_id with its own
    # LIMIT: the cost follows the account's entries, not the log's size (an OR would make the
    # planner walk the whole log backwards).
    targets = (
        (TargetType.USER, AuditEntry.target_id == account),
        (
            TargetType.VIDEO,
            AuditEntry.target_id.in_(select(Video.id).where(Video.owner_id == account)),
        ),
        (
            TargetType.COMMENT,
            AuditEntry.target_id.in_(select(Comment.id).where(Comment.author_id == account)),
        ),
    )
    branches = union_all(
        *(
            _newest(query.where(AuditEntry.target_type == kind, target), before, limit)
            for kind, target in targets
        )
    ).subquery()
    entry = aliased(AuditEntry, branches)
    merged = select(entry).order_by(entry.id.desc()).limit(limit)
    return (await db.scalars(merged)).all()


def _newest(query: Select[AuditEntry], before: UUID | None, limit: int) -> Select[AuditEntry]:
    if before is not None:
        query = query.where(AuditEntry.id < before)
    return query.order_by(AuditEntry.id.desc()).limit(limit)


async def users_by_ids(db: AsyncSession, user_ids: Collection[UUID]) -> dict[UUID, User]:
    users = await db.scalars(select(User).where(User.id.in_(user_ids)))
    return {user.id: user for user in users}


async def videos_by_ids(db: AsyncSession, video_ids: Collection[UUID]) -> dict[UUID, Video]:
    videos = await db.scalars(select(Video).where(Video.id.in_(video_ids)))
    return {video.id: video for video in videos}


async def comments_by_ids(db: AsyncSession, comment_ids: Collection[UUID]) -> dict[UUID, Comment]:
    comments = await db.scalars(select(Comment).where(Comment.id.in_(comment_ids)))
    return {comment.id: comment for comment in comments}
