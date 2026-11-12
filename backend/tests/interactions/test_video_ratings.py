"""PUT /api/videos/{id}/rating: likes and dislikes, repeated and parallel requests, access."""

import asyncio
from collections.abc import Callable
from datetime import datetime

import pytest
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.modules.reactions import service
from app.modules.reactions.models import VideoReaction
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.interactions.conftest import (
    OWNER_EMAIL,
    VIEWER_EMAIL,
    MakeViewers,
    csrf,
    meet_after,
    posted,
    rate,
    rated,
    user_by_email,
)
from tests.videos.factories import get_video, grant, make_video

NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]


async def stored(db: AsyncSession, video: Video) -> tuple[int, list[int]]:
    """The committed like_count and the stored ratings of the video."""
    like_count = (await get_video(db, video.public_id)).like_count
    values = await db.scalars(
        select(VideoReaction.value).where(VideoReaction.target_id == video.id)
    )
    return like_count, sorted(values)


# --- Rating ---


async def test_like_counts_and_shows_on_the_video(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    assert await rated(viewer, video, "like") == {"like_count": 1, "my_rating": "like"}

    page = (await viewer.get(f"/api/videos/{video.public_id}")).json()
    assert (page["like_count"], page["my_rating"]) == (1, "like")
    assert await stored(db, video) == (1, [1])


async def test_repeated_like_counts_once(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    for _ in range(3):
        assert await rated(viewer, video, "like") == {"like_count": 1, "my_rating": "like"}

    assert await stored(db, video) == (1, [1])


async def test_rating_changes_and_is_taken_back(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await rated(viewer, video, "like")

    assert await rated(viewer, video, "dislike") == {"like_count": 0, "my_rating": "dislike"}
    assert await stored(db, video) == (0, [-1])
    assert await rated(viewer, video, "like") == {"like_count": 1, "my_rating": "like"}
    assert await rated(viewer, video, "none") == {"like_count": 0, "my_rating": "none"}
    assert await rated(viewer, video, "none") == {"like_count": 0, "my_rating": "none"}
    assert await stored(db, video) == (0, [])


async def test_rated_at_moves_only_when_the_rating_changes(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    async def rated_at() -> datetime:
        query = select(VideoReaction.rated_at).where(VideoReaction.target_id == video.id)
        return (await db.execute(query)).scalar_one()

    await rated(viewer, video, "like")
    liked_at = await rated_at()

    await rated(viewer, video, "like")
    assert await rated_at() == liked_at  # a repeated request is no new rating

    await rated(viewer, video, "dislike")
    assert await rated_at() > liked_at


async def test_rating_is_per_viewer(
    viewer: AsyncClient, guest: AsyncClient, make_viewers: MakeViewers, video: Video
) -> None:
    [other] = await make_viewers(1)
    await rated(viewer, video, "like")
    await rated(other, video, "dislike")

    for client, mine in ((viewer, "like"), (other, "dislike"), (guest, "none")):
        page = (await client.get(f"/api/videos/{video.public_id}")).json()
        assert (page["like_count"], page["my_rating"]) == (1, mine)


@pytest.mark.parametrize("body", [{"rating": "love"}, {"rating": None}, {}])
async def test_unknown_rating_is_refused(
    viewer: AsyncClient, video: Video, body: dict[str, object]
) -> None:
    response = await viewer.put(
        f"/api/videos/{video.public_id}/rating", json=body, headers=csrf(viewer)
    )

    assert response.status_code == 422


# --- Parallel requests ---

PARALLEL = 10


@pytest.fixture
def together(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Call it right before PARALLEL requests: all pass the access check before any writes."""
    return lambda: meet_after(monkeypatch, service, "get_ready", PARALLEL)


async def test_parallel_likes_of_one_user_count_once(
    viewer: AsyncClient, video: Video, db: AsyncSession, together: Callable[[], None]
) -> None:
    together()
    responses = await asyncio.gather(*(rate(viewer, video, "like") for _ in range(PARALLEL)))

    assert [response.status_code for response in responses] == [200] * PARALLEL
    assert await stored(db, video) == (1, [1])


async def test_parallel_changes_of_one_user_keep_the_count_exact(
    viewer: AsyncClient, video: Video, db: AsyncSession, together: Callable[[], None]
) -> None:
    await rated(viewer, video, "like")
    ratings = (["dislike", "none", "like"] * PARALLEL)[:PARALLEL]

    together()
    responses = await asyncio.gather(*(rate(viewer, video, rating) for rating in ratings))

    assert [response.status_code for response in responses] == [200] * PARALLEL
    like_count, values = await stored(db, video)
    assert like_count == values.count(1)  # whichever request came last
    assert len(values) <= 1


async def test_parallel_likes_of_many_users_all_count(
    make_viewers: MakeViewers, video: Video, db: AsyncSession, together: Callable[[], None]
) -> None:
    viewers = await make_viewers(PARALLEL)

    together()
    responses = await asyncio.gather(*(rate(client, video, "like") for client in viewers))

    assert [response.status_code for response in responses] == [200] * PARALLEL
    assert await stored(db, video) == (PARALLEL, [1] * PARALLEL)


# --- Access ---


async def test_guest_cannot_rate(guest: AsyncClient, video: Video, db: AsyncSession) -> None:
    response = await rate(guest, video, "like")

    assert response.status_code == 401
    assert await stored(db, video) == (0, [])


async def test_rating_needs_the_csrf_token(viewer: AsyncClient, video: Video) -> None:
    response = await viewer.put(f"/api/videos/{video.public_id}/rating", json={"rating": "like"})

    assert response.status_code == 403


async def test_unknown_video_is_not_found(viewer: AsyncClient) -> None:
    response = await viewer.put(
        "/api/videos/AAAAAAAAAAA/rating", json={"rating": "like"}, headers=csrf(viewer)
    )

    assert response.status_code == 404


async def test_private_video_is_hidden_from_strangers(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    video = await make_video(
        db, await user_by_email(db, OWNER_EMAIL), visibility=Visibility.PRIVATE
    )

    stranger = await rate(viewer, video, "like")
    assert stranger.status_code == 404
    assert stranger.json() == {"detail": "Video not found"}  # same as for no video at all

    assert await rated(owner, video, "like") == {"like_count": 1, "my_rating": "like"}
    await grant(db, video.public_id, VIEWER_EMAIL)
    assert await rated(viewer, video, "like") == {"like_count": 2, "my_rating": "like"}


@pytest.mark.parametrize("status", NOT_READY)
async def test_unfinished_video_cannot_be_rated_even_by_its_owner(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    video = await make_video(db, await user_by_email(db, OWNER_EMAIL), status=status)

    assert (await rate(owner, video, "like")).status_code == 404

    # The video API still shows the owner the video and how processing goes.
    page = await owner.get(f"/api/videos/{video.public_id}")
    assert page.status_code == 200
    assert (page.json()["status"], page.json()["my_rating"]) == (status.value, "none")


async def test_ratings_are_limited_per_account(
    owner: AsyncClient,
    viewer: AsyncClient,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "RATINGS_PER_USER", RateLimit("rating", limit=3, window=60))
    comment = (await posted(owner, video, "Root"))["id"]
    for rating in ("like", "none", "like"):
        await rated(viewer, video, rating)

    too_many = await rate(viewer, video, "none")
    assert too_many.status_code == 429
    assert int(too_many.headers["Retry-After"]) > 0
    # One budget for videos and comments; other accounts have their own.
    on_comment = await viewer.put(
        f"/api/comments/{comment}/rating", json={"rating": "like"}, headers=csrf(viewer)
    )
    assert on_comment.status_code == 429
    assert (await rate(owner, video, "like")).status_code == 200
