"""Rating rules, the same for videos and comments. The service commits, like @Transactional."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments import service as comments
from app.modules.reactions import repository as reactions
from app.modules.reactions.models import LIKE, CommentReaction, VideoReaction
from app.modules.reactions.repository import Table
from app.modules.reactions.schemas import Rating, RatingOut
from app.modules.users.models import User
from app.modules.videos.interactions import get_ready


async def my_rating(db: AsyncSession, user: User | None, video_id: UUID) -> Rating:
    value = await reactions.get_value(db, VideoReaction, video_id, user.id) if user else None
    return Rating.of(value)


async def rate_video(db: AsyncSession, user: User, public_id: str, rating: Rating) -> RatingOut:
    video = await get_ready(db, user, public_id)
    return await _rate(db, user, rating, VideoReaction, video.id, video.like_count)


async def rate_comment(db: AsyncSession, user: User, comment_id: UUID, rating: Rating) -> RatingOut:
    comment, _ = await comments.get_readable(db, user, comment_id)
    return await _rate(db, user, rating, CommentReaction, comment.id, comment.like_count)


async def _rate(
    db: AsyncSession,
    user: User,
    rating: Rating,
    table: Table,
    target_id: UUID,
    like_count: int,
) -> RatingOut:
    """Idempotent: sending the same rating again changes nothing."""
    value = rating.stored
    if value is None:
        old = await reactions.delete_value(db, table, target_id, user.id)
    else:
        old = await reactions.put_value(db, table, target_id, user.id, value)
    # Counted from what the statement really replaced, so parallel requests add up exactly.
    delta = (value == LIKE) - (old == LIKE)
    if delta:
        like_count = await reactions.add_likes(db, table, target_id, delta)
    await db.commit()
    return RatingOut(like_count=like_count, my_rating=rating)
