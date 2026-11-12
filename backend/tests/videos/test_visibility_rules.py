"""The visibility rules agree with each other, on every kind of video and viewer.

- `can_view` (videos/access.py): may this viewer open this one video?
- `viewable` (videos/access.py): the same as a SQL condition, for lists (playlists).
- `interactable` (videos/access.py): `can_interact` as a SQL condition, for Liked videos.
- `LISTED` (videos/repository.py): may the video appear in public lists? The same for every
  viewer, the owner too.
- `LISTED_SQL` (videos/models.py): the condition of the partial indexes; LISTED must imply it.

One matrix, one oracle (here and in test_access.py): a new axis goes into both, then every rule
must follow, or these tests fail. Moderation's axes: hidden, and the owner's status (ADR 0009).
"""

from itertools import product
from uuid import UUID

import pytest
from sqlalchemy import ColumnElement, TextClause, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User, UserStatus
from app.modules.videos.access import can_interact, can_view, interactable, viewable
from app.modules.videos.models import LISTED_SQL, Video, VideoAccess, VideoStatus, Visibility
from app.modules.videos.repository import LISTED
from tests.videos.factories import make_user, make_video
from tests.videos.test_access import Viewer, expected

type State = tuple[Visibility, VideoStatus, bool, UserStatus]  # ..., hidden, owner's status

VIDEO_STATES: list[State] = list(product(Visibility, VideoStatus, [False, True], UserStatus))


def listed(visibility: Visibility, status: VideoStatus, hidden: bool, owner: UserStatus) -> bool:
    public = visibility is Visibility.PUBLIC and status is VideoStatus.READY
    return public and not hidden and owner is not UserStatus.TERMINATED


def judged_as(viewer: Viewer, state: State) -> Viewer:
    """OWNER owns the active channel only: on the other channels' videos it is a stranger."""
    on_another_channel = state[3] is not UserStatus.ACTIVE
    return Viewer.STRANGER if viewer is Viewer.OWNER and on_another_channel else viewer


@pytest.fixture
async def owners(db: AsyncSession) -> dict[UserStatus, User]:
    """A channel per account status."""
    owners = {status: await make_user(db, f"owner-{status}") for status in UserStatus}
    for status, owner in owners.items():
        owner.status = status
    await db.commit()
    return owners


@pytest.fixture
async def videos(db: AsyncSession, owners: dict[UserStatus, User]) -> dict[State, Video]:
    """One video of each state, on the channel of its owner's status."""
    videos: dict[State, Video] = {}
    for visibility, status, hidden, owner_status in VIDEO_STATES:
        video = await make_video(db, owners[owner_status], visibility=visibility, status=status)
        video.is_hidden = hidden
        videos[visibility, status, hidden, owner_status] = video
    await db.commit()
    return videos


@pytest.fixture
async def viewers(
    db: AsyncSession, owners: dict[UserStatus, User], videos: dict[State, Video]
) -> dict[Viewer, User | None]:
    """Every kind of viewer; GRANTED may watch every private video of the matrix."""
    granted = await make_user(db, "carl")
    db.add_all(VideoAccess(video_id=video.id, user_id=granted.id) for video in videos.values())
    await db.commit()
    return {
        Viewer.GUEST: None,
        Viewer.STRANGER: await make_user(db, "bob"),
        Viewer.GRANTED: granted,
        Viewer.OWNER: owners[UserStatus.ACTIVE],
        Viewer.MODERATOR: await make_user(db, "mod", Role.MODERATOR),
        Viewer.ADMIN: await make_user(db, "admin", Role.ADMIN),
    }


async def ids_where(db: AsyncSession, *condition: ColumnElement[bool] | TextClause) -> set[UUID]:
    return set(await db.scalars(select(Video.id).where(*condition)))


async def test_listed_is_public_ready_and_unrestricted(
    db: AsyncSession, videos: dict[State, Video]
) -> None:
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


@pytest.mark.parametrize("viewer", list(Viewer))
async def test_viewable_is_can_view_as_sql(
    db: AsyncSession,
    videos: dict[State, Video],
    viewers: dict[Viewer, User | None],
    viewer: Viewer,
) -> None:
    user = viewers[viewer]
    allowed = {video.id for video in videos.values() if await can_view(db, user, video)}

    assert await ids_where(db, viewable(user)) == allowed
    # And both follow the policy's oracle, so a rule can't drift in both at once.
    oracle = {
        video.id for state, video in videos.items() if expected(judged_as(viewer, state), *state)
    }
    assert allowed == oracle


@pytest.mark.parametrize("viewer", list(Viewer))
async def test_interactable_is_can_interact_as_sql(
    db: AsyncSession,
    videos: dict[State, Video],
    viewers: dict[Viewer, User | None],
    viewer: Viewer,
) -> None:
    user = viewers[viewer]
    allowed = {video.id for video in videos.values() if await can_interact(db, user, video)}

    assert await ids_where(db, interactable(user)) == allowed


async def test_a_grant_on_another_video_opens_nothing_here(
    db: AsyncSession, videos: dict[State, Video], viewers: dict[Viewer, User | None]
) -> None:
    """viewable ties a grant to its own row: a grant elsewhere is a stranger's view here."""
    elsewhere = await make_video(db, await make_user(db, "dave"), visibility=Visibility.PRIVATE)
    granted_elsewhere = await make_user(db, "erin")
    db.add(VideoAccess(video_id=elsewhere.id, user_id=granted_elsewhere.id))
    await db.commit()
    here = Video.id.in_([video.id for video in videos.values()])

    assert await ids_where(db, viewable(granted_elsewhere), here) == await ids_where(
        db, viewable(viewers[Viewer.STRANGER]), here
    )
