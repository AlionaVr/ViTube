"""The view policy (ADR 0004): who may watch which video."""

from enum import Enum

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.users.models import Role, User, UserStatus
from app.modules.users.schemas import ChannelSummary
from app.modules.videos.access import can_view, get_viewable
from app.modules.videos.models import VideoAccess, VideoStatus, Visibility
from tests.videos.factories import make_user, make_video


class Viewer(Enum):
    GUEST = "guest"
    STRANGER = "stranger"
    GRANTED = "granted"  # in video_access
    OWNER = "owner"
    MODERATOR = "moderator"
    ADMIN = "admin"


def expected(
    viewer: Viewer,
    visibility: Visibility,
    status: VideoStatus,
    hidden: bool = False,
    owner_status: UserStatus = UserStatus.ACTIVE,
) -> bool:
    if viewer in (Viewer.OWNER, Viewer.MODERATOR, Viewer.ADMIN):
        return True
    if status is not VideoStatus.READY or hidden or owner_status is UserStatus.TERMINATED:
        return False  # restricted by moderation (ADR 0009); a ban keeps content
    return visibility is not Visibility.PRIVATE or viewer is Viewer.GRANTED


async def viewer_user(db: AsyncSession, viewer: Viewer, owner: User) -> User | None:
    match viewer:
        case Viewer.GUEST:
            return None
        case Viewer.OWNER:
            return owner
        case Viewer.MODERATOR:
            return await make_user(db, "mod", Role.MODERATOR)
        case Viewer.ADMIN:
            return await make_user(db, "admin", Role.ADMIN)
        case _:
            return await make_user(db, "bob")


@pytest.mark.parametrize("status", list(VideoStatus))
@pytest.mark.parametrize("visibility", list(Visibility))
@pytest.mark.parametrize("viewer", list(Viewer))
async def test_can_view(
    db: AsyncSession, viewer: Viewer, visibility: Visibility, status: VideoStatus
) -> None:
    owner = await make_user(db, "anna")
    video = await make_video(db, owner, visibility=visibility, status=status)
    user = await viewer_user(db, viewer, owner)
    if viewer is Viewer.GRANTED and user is not None:
        db.add(VideoAccess(video_id=video.id, user_id=user.id))
        await db.commit()

    assert await can_view(db, user, video) is expected(viewer, visibility, status)


@pytest.mark.parametrize("owner_status", list(UserStatus))
@pytest.mark.parametrize("hidden", [False, True])
@pytest.mark.parametrize("viewer", list(Viewer))
async def test_can_view_under_moderation(
    db: AsyncSession, viewer: Viewer, hidden: bool, owner_status: UserStatus
) -> None:
    """A public, ready video: what moderation takes away. Every state: test_visibility_rules."""
    owner = await make_user(db, "anna")
    video = await make_video(db, owner)
    video.is_hidden, owner.status = hidden, owner_status
    await db.commit()
    user = await viewer_user(db, viewer, owner)

    assert await can_view(db, user, video) is expected(
        viewer, Visibility.PUBLIC, VideoStatus.READY, hidden, owner_status
    )


async def test_a_grant_on_another_video_gives_no_access(db: AsyncSession) -> None:
    owner, bob = await make_user(db, "anna"), await make_user(db, "bob")
    shared = await make_video(db, owner, visibility=Visibility.PRIVATE)
    other = await make_video(db, owner, visibility=Visibility.PRIVATE)
    db.add(VideoAccess(video_id=shared.id, user_id=bob.id))
    await db.commit()

    assert await can_view(db, bob, other) is False


async def test_get_viewable_returns_the_video(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"))

    assert (await get_viewable(db, None, video.public_id)).id == video.id


async def test_get_viewable_hides_private_videos_as_not_found(db: AsyncSession) -> None:
    video = await make_video(db, await make_user(db, "anna"), visibility=Visibility.PRIVATE)
    stranger = await make_user(db, "bob")

    # Same error as for an unknown id: a stranger can't tell the two apart.
    with pytest.raises(NotFound) as private:
        await get_viewable(db, stranger, video.public_id)
    with pytest.raises(NotFound) as unknown:
        await get_viewable(db, stranger, "nosuchvideo")
    assert private.value.detail == unknown.value.detail


async def test_channel_summary_uses_the_handle_until_channels_have_names(db: AsyncSession) -> None:
    user = await make_user(db, "anna")

    assert ChannelSummary.of(user) == ChannelSummary(handle="anna", name="anna", avatar_url=None)
