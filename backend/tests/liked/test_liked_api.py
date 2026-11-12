"""GET /api/me/liked and /api/me/liked/items: the user's likes as a playlist, newest like first."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx2 import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.liked import service
from app.modules.reactions.models import LIKE, VideoReaction
from app.modules.users.models import User, UserStatus
from app.modules.videos.models import Video, VideoStatus
from tests.history.conftest import make_private
from tests.interactions.conftest import VIEWER_EMAIL, rated, user_by_email
from tests.moderation.conftest import hide_directly
from tests.videos.factories import grant, make_user, make_video, set_status


async def summary(client: AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/me/liked")
    assert response.status_code == 200, response.text
    return response.json()


async def page(client: AsyncClient, cursor: str | None = None) -> dict[str, Any]:
    response = await client.get("/api/me/liked/items", params={"cursor": cursor} if cursor else {})
    assert response.status_code == 200, response.text
    return response.json()


async def liked(client: AsyncClient) -> list[str]:
    """Public ids of every page, newest like first. The header counts what the list shows."""
    ids: list[str] = []
    cursor = None
    while True:
        body = await page(client, cursor)
        ids += [item["video"]["id"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            assert (await summary(client))["video_count"] == len(ids)
            return ids


# --- The list ---


async def test_guest_gets_401(guest: AsyncClient) -> None:
    assert (await guest.get("/api/me/liked")).status_code == 401
    assert (await guest.get("/api/me/liked/items")).status_code == 401


async def test_user_without_likes_gets_an_empty_list(viewer: AsyncClient, db: AsyncSession) -> None:
    me = await user_by_email(db, VIEWER_EMAIL)

    assert await summary(viewer) == {
        "video_count": 0,
        "thumbnail_url": None,
        "updated_at": None,
        "owner": {"handle": me.handle, "name": me.handle, "avatar_url": None},
    }
    assert await page(viewer) == {"items": [], "next_cursor": None}


async def test_likes_come_newest_first_and_the_newest_is_the_cover(
    viewer: AsyncClient, db: AsyncSession
) -> None:
    channel = await make_user(db, "anna")
    first, second, third = [await make_video(db, channel) for _ in range(3)]
    for video in (first, third, second):  # not in upload order
        await rated(viewer, video, "like")

    items = (await page(viewer))["items"]

    assert [item["video"]["id"] for item in items] == [
        second.public_id,
        third.public_id,
        first.public_id,
    ]
    times = [datetime.fromisoformat(item["liked_at"]) for item in items]
    assert times == sorted(times, reverse=True)
    assert all(time.tzinfo is not None for time in times)
    assert items[0]["video"]["channel"]["handle"] == channel.handle  # the video's, not mine
    header = await summary(viewer)
    assert (header["video_count"], header["thumbnail_url"], header["updated_at"]) == (
        3,
        f"/media/thumbs/{second.id}.jpg",
        items[0]["liked_at"],
    )


async def test_unliked_and_disliked_videos_are_not_listed(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    disliked = await make_video(db, await make_user(db, "anna"))
    await rated(viewer, video, "like")
    await rated(viewer, disliked, "dislike")
    assert await liked(viewer) == [video.public_id]

    await rated(viewer, video, "none")

    assert await liked(viewer) == []
    assert (await summary(viewer))["thumbnail_url"] is None


@pytest.mark.parametrize("between", ["none", "dislike"])
async def test_liking_again_moves_the_video_to_the_top(
    viewer: AsyncClient, video: Video, db: AsyncSession, between: str
) -> None:
    other = await make_video(db, await make_user(db, "anna"))
    await rated(viewer, video, "like")
    await rated(viewer, other, "like")

    await rated(viewer, video, between)
    await rated(viewer, video, "like")

    assert await liked(viewer) == [video.public_id, other.public_id]


async def test_repeated_like_keeps_its_place(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    other = await make_video(db, await make_user(db, "anna"))
    await rated(viewer, video, "like")
    await rated(viewer, other, "like")

    await rated(viewer, video, "like")

    assert await liked(viewer) == [other.public_id, video.public_id]


async def test_another_users_likes_are_not_in_my_list(
    owner: AsyncClient, viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    other = await make_video(db, await make_user(db, "anna"))
    await rated(owner, video, "like")
    await rated(viewer, other, "like")

    assert await liked(owner) == [video.public_id]
    assert await liked(viewer) == [other.public_id]


# --- Which videos ---


async def test_video_turned_private_leaves_a_strangers_list_until_a_grant(
    viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await rated(viewer, video, "like")

    await make_private(db, video)
    assert await liked(viewer) == []
    header = await summary(viewer)
    assert (header["thumbnail_url"], header["updated_at"]) == (None, None)  # no trace of it

    await grant(db, video.public_id, VIEWER_EMAIL)
    assert await liked(viewer) == [video.public_id]


async def test_owner_and_moderator_keep_a_liked_video_that_turned_private(
    owner: AsyncClient, moderator: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await rated(owner, video, "like")
    await rated(moderator, video, "like")

    await make_private(db, video)

    assert await liked(owner) == [video.public_id]
    assert await liked(moderator) == [video.public_id]


@pytest.mark.parametrize("restriction", ["hidden", "terminated"])
async def test_restricted_video_leaves_the_list_for_all_but_moderators(
    viewer: AsyncClient, moderator: AsyncClient, video: Video, db: AsyncSession, restriction: str
) -> None:
    await rated(viewer, video, "like")
    await rated(moderator, video, "like")

    if restriction == "hidden":
        await hide_directly(db, video)
    else:
        terminate = update(User).where(User.id == video.owner_id)
        await db.execute(terminate.values(status=UserStatus.TERMINATED))
        await db.commit()

    assert await liked(viewer) == []
    assert await liked(moderator) == [video.public_id]


async def test_video_no_longer_ready_is_not_listed_even_to_owner_or_moderator(
    owner: AsyncClient, moderator: AsyncClient, video: Video, db: AsyncSession
) -> None:
    await rated(owner, video, "like")
    await rated(moderator, video, "like")

    await set_status(db, video.public_id, VideoStatus.PROCESSING)

    assert await liked(owner) == []
    assert await liked(moderator) == []


# --- Pages ---


async def test_pages_go_newest_first_without_gaps_or_repeats(
    viewer: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "PAGE_SIZE", 2)
    me, channel = await user_by_email(db, VIEWER_EMAIL), await make_user(db, "anna")
    start = datetime.now(UTC)
    # Three likes share each time, so pages end inside a tie: video_id breaks it.
    likes = [(start + timedelta(seconds=n // 3), await make_video(db, channel)) for n in range(7)]
    db.add_all(
        VideoReaction(user_id=me.id, target_id=video.id, value=LIKE, rated_at=at)
        for at, video in likes
    )
    await db.commit()

    first = await page(viewer)

    expected = sorted(likes, key=lambda pair: (pair[0], pair[1].id), reverse=True)
    assert len(first["items"]) == 2
    assert await liked(viewer) == [video.public_id for _, video in expected]


@pytest.mark.parametrize(
    "cursor",
    [
        "not base64!",
        encode_cursor(("x",)),
        encode_cursor(("2026-11-12T10:00:00Z", "not a uuid")),
        encode_cursor(("2026-11-12T10:00:00", str(uuid4()))),  # no time zone
        encode_cursor(("2026-11-12T10:00:00Z", str(uuid4()), 1)),
    ],
)
async def test_bad_cursor_gets_400(viewer: AsyncClient, cursor: str) -> None:
    response = await viewer.get("/api/me/liked/items", params={"cursor": cursor})

    assert response.status_code == 400


async def test_overlong_cursor_gets_422(viewer: AsyncClient) -> None:
    response = await viewer.get("/api/me/liked/items", params={"cursor": "a" * 201})

    assert response.status_code == 422
