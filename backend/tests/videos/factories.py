"""Rows for video tests, read and written straight to the DB."""

import secrets

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User
from app.modules.videos.models import Video, VideoAccess, VideoStatus, Visibility


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


async def get_video(db: AsyncSession, public_id: str) -> Video:
    """The row as committed now, not as this session last saw it."""
    query = select(Video).where(Video.public_id == public_id)
    video = await db.scalar(query.execution_options(populate_existing=True))
    assert video is not None
    return video


async def set_status(db: AsyncSession, public_id: str, status: VideoStatus) -> Video:
    """Move a video to any status, as the worker would."""
    video = await get_video(db, public_id)
    video.status = status
    # What the state rules (CHECKs) require.
    video.duration_sec = 10 if status is VideoStatus.READY else None
    video.error_message = "Not a video" if status is VideoStatus.FAILED else None
    await db.commit()
    return video


async def grant(db: AsyncSession, public_id: str, email: str) -> None:
    """Let the user with this email watch the private video."""
    video = await get_video(db, public_id)
    user_id = await db.scalar(select(User.id).where(User.email == email))
    assert user_id is not None
    db.add(VideoAccess(video_id=video.id, user_id=user_id))
    await db.commit()


async def set_role(db: AsyncSession, email: str, role: Role) -> None:
    await db.execute(update(User).where(User.email == email).values(role=role))
    await db.commit()
