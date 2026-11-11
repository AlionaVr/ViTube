"""Comment rules. The service commits, like @Transactional."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.core.pagination import Page, decode_cursor, split_page
from app.modules.comments import repository as comments
from app.modules.comments.models import Comment
from app.modules.comments.repository import CommentRow
from app.modules.comments.schemas import CommentIn, CommentOut, CommentSort
from app.modules.reactions import repository as reactions
from app.modules.reactions.models import CommentReaction
from app.modules.reactions.schemas import Rating
from app.modules.users.models import User
from app.modules.videos import repository as videos
from app.modules.videos.interactions import get_ready, is_ready
from app.modules.videos.models import Video

PAGE_SIZE = 20
# A cursor is client input: a number the column can't hold must give 400, not a DB error.
_TopKey = tuple[Annotated[int, Field(ge=0, le=2**31 - 1)], UUID]  # (like_count, id)


async def list_comments(
    db: AsyncSession, user: User | None, public_id: str, sort: CommentSort, cursor: str | None
) -> Page[CommentOut]:
    video = await get_ready(db, user, public_id)
    if sort is CommentSort.TOP:
        after = decode_cursor(cursor, _TopKey) if cursor else None
        rows = await comments.list_top(db, video.id, after=after, limit=PAGE_SIZE + 1)
        page, next_cursor = split_page(rows, PAGE_SIZE, lambda row: (row[0].like_count, row[0].id))
    else:
        before = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
        rows = await comments.list_newest(db, video.id, before=before, limit=PAGE_SIZE + 1)
        page, next_cursor = split_page(rows, PAGE_SIZE, lambda row: (row[0].id,))
    return Page(items=await _items(db, user, page, video), next_cursor=next_cursor)


async def list_replies(
    db: AsyncSession, user: User | None, comment_id: UUID, cursor: str | None
) -> Page[CommentOut]:
    root, video = await get_readable(db, user, comment_id)
    after = decode_cursor(cursor, tuple[UUID])[0] if cursor else None
    rows = await comments.list_replies(db, root.id, after=after, limit=PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, PAGE_SIZE, lambda row: (row[0].id,))
    return Page(items=await _items(db, user, page, video), next_cursor=next_cursor)


async def add_comment(db: AsyncSession, user: User, public_id: str, data: CommentIn) -> CommentOut:
    video = await get_ready(db, user, public_id)
    root_id = None
    if data.parent_id is not None:
        parent = await comments.get(db, data.parent_id)
        if parent is None or parent.video_id != video.id or parent.is_deleted:
            raise NotFound("Comment not found")
        root_id = parent.parent_id or parent.id  # one level: replies go to the thread root
    # Locks first, in one order for all: the thread root, then the video. The insert comes last,
    # under them: posts to one list take ids in commit order, so a reader paging by id never
    # passes an id whose comment commits later.
    if root_id is not None and not await comments.add_reply(db, root_id):
        raise NotFound("Comment not found")  # deleted meanwhile: nothing written yet
    await comments.add_comment(db, video.id)
    comment = await comments.insert_comment(
        db, video_id=video.id, author_id=user.id, parent_id=root_id, text=data.text
    )
    await db.commit()
    return CommentOut.of(comment, user, video.owner_id)


async def get_readable(
    db: AsyncSession, user: User | None, comment_id: UUID
) -> tuple[Comment, Video]:
    """The comment and its video, or NotFound if either is missing, deleted or hidden from the
    viewer."""
    comment = await comments.get(db, comment_id)
    video = (
        await videos.get_by_id(db, comment.video_id) if comment and not comment.is_deleted else None
    )
    if comment is None or video is None or not await is_ready(db, user, video):
        raise NotFound("Comment not found")
    return comment, video


async def _items(
    db: AsyncSession, user: User | None, page: Sequence[CommentRow], video: Video
) -> list[CommentOut]:
    ids = [comment.id for comment, _ in page]
    mine = await reactions.get_values(db, CommentReaction, ids, user.id) if user and ids else {}
    return [
        CommentOut.of(comment, author, video.owner_id, Rating.of(mine.get(comment.id)))
        for comment, author in page
    ]
