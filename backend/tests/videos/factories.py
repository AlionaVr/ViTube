"""Rows for video tests, written straight to the DB."""

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User
from app.modules.videos.models import Video, VideoStatus, Visibility


async def make_user(db: AsyncSession, name: str, role: Role = Role.USER) -> User:
    user = User(email=f"{name}@example.com", handle=name, password_hash="hash", role=role)
    db.add(user)
    await db.commit()
    return user


async def make_video(
    db: AsyncSession,
    owner: User,
    *,
    visibility: Visibility = Visibility.PUBLIC,
    status: VideoStatus = VideoStatus.READY,
) -> Video:
    video = Video(
        public_id=secrets.token_urlsafe(8),  # 11 URL-safe chars
        owner_id=owner.id,
        title="A video",
        visibility=visibility,
        status=status,
        # What the state rules (CHECKs) require.
        duration_sec=10 if status is VideoStatus.READY else None,
        error_message="Not a video" if status is VideoStatus.FAILED else None,
    )
    db.add(video)
    await db.commit()
    return video
