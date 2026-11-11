"""The visibility rules agree with each other, on every kind of video and viewer.

- `can_view` (videos/access.py): may this viewer open this one video?
- `LISTED` (videos/repository.py): may the video appear in public lists? The same for every
  viewer, the owner too.
- `LISTED_SQL` (videos/models.py): the condition of the partial indexes; LISTED must imply it.

One matrix, one oracle. Moderation adds `hidden` and `owner_status` axes to VIDEO_STATES and to
the oracles here and in test_access.py; then every rule must follow, or these tests fail.
"""

from itertools import product
from uuid import UUID

import pytest
from sqlalchemy import ColumnElement, TextClause, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User
from app.modules.videos.access import can_view
from app.modules.videos.models import LISTED_SQL, Video, VideoAccess, VideoStatus, Visibility
from app.modules.videos.repository import LISTED
from tests.videos.factories import make_user, make_video
from tests.videos.test_access import Viewer

type State = tuple[Visibility, VideoStatus]

VIDEO_STATES: list[State] = list(product(Visibility, VideoStatus))


def listed(visibility: Visibility, status: VideoStatus) -> bool:
    return visibility is Visibility.PUBLIC and status is VideoStatus.READY


@pytest.fixture
async def videos(db: AsyncSession) -> dict[State, Video]:
    """One video of each state, all on one channel."""
    owner = await make_user(db, "anna")
    return {
        (visibility, status): await make_video(db, owner, visibility=visibility, status=status)
        for visibility, status in VIDEO_STATES
    }


@pytest.fixture
async def viewers(db: AsyncSession, videos: dict[State, Video]) -> dict[Viewer, User | None]:
    """Every kind of viewer; GRANTED may watch every private video of the matrix."""
    granted = await make_user(db, "carl")
    db.add_all(VideoAccess(video_id=video.id, user_id=granted.id) for video in videos.values())
    await db.commit()
    owner = await db.get_one(User, next(iter(videos.values())).owner_id)
    return {
        Viewer.GUEST: None,
        Viewer.STRANGER: await make_user(db, "bob"),
        Viewer.GRANTED: granted,
        Viewer.OWNER: owner,
        Viewer.MODERATOR: await make_user(db, "mod", Role.MODERATOR),
        Viewer.ADMIN: await make_user(db, "admin", Role.ADMIN),
    }


async def ids_where(db: AsyncSession, *condition: ColumnElement[bool] | TextClause) -> set[UUID]:
    return set(await db.scalars(select(Video.id).where(*condition)))


async def test_listed_is_public_and_ready(db: AsyncSession, videos: dict[State, Video]) -> None:
    expected = {video.id for state, video in videos.items() if listed(*state)}

    assert await ids_where(db, *LISTED) == expected


async def test_listed_implies_the_partial_index_condition(
    db: AsyncSession, videos: dict[State, Video]
) -> None:
    # Otherwise a list query can't use the ix_videos_listed_* indexes.
    assert await ids_where(db, *LISTED) <= await ids_where(db, text(LISTED_SQL))


@pytest.mark.parametrize("viewer", list(Viewer))
async def test_every_viewer_may_watch_every_listed_video(
    db: AsyncSession,
    videos: dict[State, Video],
    viewers: dict[Viewer, User | None],
    viewer: Viewer,
) -> None:
    for state, video in videos.items():
        if listed(*state):
            assert await can_view(db, viewers[viewer], video), (viewer, state)
