"""Comments and replies. Guests read; signed-in users write."""

from uuid import UUID

from fastapi import APIRouter, status

from app.core.pagination import Cursor, Page
from app.db.session import DbSession
from app.modules.auth.deps import CurrentUser, OptionalUser
from app.modules.comments import service
from app.modules.comments.schemas import CommentIn, CommentOut, CommentSort
from app.modules.videos.schemas import PublicId

router = APIRouter(prefix="/api", tags=["comments"])


@router.get(
    "/videos/{public_id}/comments",
    response_model=Page[CommentOut],
    summary="A video's comments, without replies",
)
async def list_comments(
    public_id: PublicId,
    user: OptionalUser,
    db: DbSession,
    sort: CommentSort = CommentSort.TOP,
    cursor: Cursor = None,
) -> Page[CommentOut]:
    return await service.list_comments(db, user, public_id, sort, cursor)


@router.post(
    "/videos/{public_id}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=CommentOut,
    summary="Comment on a video or reply to a comment",
)
async def add_comment(
    public_id: PublicId, body: CommentIn, user: CurrentUser, db: DbSession
) -> CommentOut:
    return await service.add_comment(db, user, public_id, body)


@router.get(
    "/comments/{comment_id}/replies",
    response_model=Page[CommentOut],
    summary="Replies to a comment, oldest first",
)
async def list_replies(
    comment_id: UUID, user: OptionalUser, db: DbSession, cursor: Cursor = None
) -> Page[CommentOut]:
    return await service.list_replies(db, user, comment_id, cursor)
