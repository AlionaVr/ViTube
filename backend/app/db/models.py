"""Model registry. Import every module's models here so Alembic autogenerate sees them."""

from app.db.base import Base
from app.modules.reactions.models import VideoReaction
from app.modules.users.models import User
from app.modules.videos.models import Video, VideoAccess

__all__ = ["Base", "User", "Video", "VideoAccess", "VideoReaction"]
