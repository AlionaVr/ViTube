from pydantic import BaseModel

from app.modules.users.models import User


class ChannelSummary(BaseModel):
    """What a video card or a comment shows about a user's channel."""

    handle: str
    name: str
    avatar_url: str | None

    @classmethod
    def of(cls, user: User) -> "ChannelSummary":
        # Channel names and avatars come with channels (Stage 6); until then the handle is the name.
        return cls(handle=user.handle, name=user.handle, avatar_url=None)
