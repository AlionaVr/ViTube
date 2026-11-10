import enum
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.modules.comments.models import TEXT_MAX, Comment
from app.modules.users.models import User
from app.modules.users.schemas import ChannelSummary

CommentText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TEXT_MAX)
]


class CommentSort(enum.StrEnum):
    TOP = "top"  # most liked first
    NEW = "new"


class CommentIn(BaseModel):
    text: CommentText
    parent_id: UUID | None = Field(
        default=None, description="The comment to reply to. A reply to a reply joins its thread."
    )


class CommentOut(BaseModel):
    id: UUID
    author: ChannelSummary
    by_owner: bool = Field(description="Written by the video's owner")
    text: str
    published_at: datetime
    like_count: int
    reply_count: int

    @classmethod
    def of(cls, comment: Comment, author: User, video_owner_id: UUID) -> "CommentOut":
        return cls(
            id=comment.id,
            author=ChannelSummary.of(author),
            by_owner=comment.author_id == video_owner_id,
            text=comment.text,
            published_at=comment.created_at,
            like_count=comment.like_count,
            reply_count=comment.reply_count,
        )
