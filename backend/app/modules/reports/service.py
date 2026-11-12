"""Reporting rules. The service commits, like @Transactional."""

from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError, NotFound
from app.core.rate_limit import RateLimit
from app.modules.comments import service as comments
from app.modules.reports import repository as reports
from app.modules.reports.schemas import ReportIn
from app.modules.users.models import User
from app.modules.videos.interactions import get_ready

# Counted before any check, per account: a script can't flood the queue.
REPORTS_PER_USER = RateLimit("report", limit=20, window=60 * 60)


async def report_video(
    db: AsyncSession, redis: Redis, user: User, public_id: str, data: ReportIn
) -> None:
    """Report a video the user may watch. Reporting it again while open changes nothing."""
    await REPORTS_PER_USER.hit(redis, str(user.id))
    video = await get_ready(db, user, public_id)
    if video.owner_id == user.id:
        raise DomainError("You can't report your own video")
    if not await reports.lock_open_video(db, video.id):
        raise NotFound("Video not found")  # hidden meanwhile
    await reports.add(
        db, reporter_id=user.id, video_id=video.id, reason=data.reason, details=data.details
    )
    await db.commit()


async def report_comment(
    db: AsyncSession, redis: Redis, user: User, comment_id: UUID, data: ReportIn
) -> None:
    """Report a comment the user may read. Reporting it again while open changes nothing."""
    await REPORTS_PER_USER.hit(redis, str(user.id))
    comment, video = await comments.get_readable(db, user, comment_id)
    if comment.author_id == user.id:
        raise DomainError("You can't report your own comment")
    if not await reports.lock_open_comment(db, comment.id, video.id):
        raise NotFound("Comment not found")  # deleted or its video hidden meanwhile
    await reports.add(
        db, reporter_id=user.id, comment_id=comment.id, reason=data.reason, details=data.details
    )
    await db.commit()
