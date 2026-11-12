"""Model registry. Import every module's models here so Alembic autogenerate sees them."""

from app.db.base import Base
from app.modules.audit.models import AuditEntry
from app.modules.channels.models import Subscription
from app.modules.comments.models import Comment
from app.modules.history.models import HistoryEntry
from app.modules.moderation import models as moderation_indexes  # noqa: F401  # registers indexes
from app.modules.playlists.models import Playlist, PlaylistItem
from app.modules.reactions.models import CommentReaction, VideoReaction
from app.modules.reports.models import Report
from app.modules.users.models import User
from app.modules.videos.models import Video, VideoAccess

__all__ = [
    "AuditEntry",
    "Base",
    "Comment",
    "CommentReaction",
    "HistoryEntry",
    "Playlist",
    "PlaylistItem",
    "Report",
    "Subscription",
    "User",
    "Video",
    "VideoAccess",
    "VideoReaction",
]
