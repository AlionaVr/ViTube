"""Model registry. Import every module's models here so Alembic autogenerate sees them."""

from app.db.base import Base
from app.modules.channels.models import Subscription
from app.modules.comments.models import Comment
from app.modules.reactions.models import CommentReaction, VideoReaction
from app.modules.users.models import User
from app.modules.videos.models import Video, VideoAccess

__all__ = [
    "Base",
    "Comment",
    "CommentReaction",
    "Subscription",
    "User",
    "Video",
    "VideoAccess",
    "VideoReaction",
]
