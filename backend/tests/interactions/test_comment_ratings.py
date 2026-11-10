"""PUT /api/comments/{id}/rating: likes of comments and replies, my_rating in lists, access."""

import asyncio
from uuid import UUID, uuid4

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments import service as comments_service
from app.modules.comments.models import Comment
from app.modules.reactions.models import CommentReaction
from app.modules.videos.models import Video, Visibility
from tests.interactions.conftest import (
    OWNER_EMAIL,
    VIEWER_EMAIL,
    MakeViewers,
    comments_of,
    csrf,
    meet_after,
    posted,
    replies_to,
    user_by_email,
)
from tests.videos.factories import grant, make_video

PARALLEL = 10


async def rate(client: AsyncClient, comment_id: object, rating: str) -> Response:
    return await client.put(
        f"/api/comments/{comment_id}/rating", json={"rating": rating}, headers=csrf(client)
    )


async def rated(client: AsyncClient, comment_id: object, rating: str) -> dict[str, object]:
    response = await rate(client, comment_id, rating)
    assert response.status_code == 200
    return response.json()


async def stored(db: AsyncSession, comment_id: object) -> tuple[int, list[int]]:
    """The committed like_count and the stored ratings of the comment."""
    key = UUID(str(comment_id))
    like_count = (
        await db.execute(select(Comment.like_count).where(Comment.id == key))
    ).scalar_one()
    values = await db.scalars(select(CommentReaction.value).where(CommentReaction.target_id == key))
    return like_count, sorted(values)


def mine(response: Response) -> list[tuple[int, str]]:
    """(like_count, my_rating) of each comment in a list."""
    assert response.status_code == 200
    return [(item["like_count"], item["my_rating"]) for item in response.json()["items"]]


@pytest.fixture
async def comment(owner: AsyncClient, video: Video) -> str:
    """A top-level comment by the video's owner; its id."""
    return str((await posted(owner, video, "Root"))["id"])


# --- Rating ---


async def test_like_counts_and_shows_in_the_lists(
    owner: AsyncClient,
    viewer: AsyncClient,
    guest: AsyncClient,
    video: Video,
    comment: str,
    db: AsyncSession,
) -> None:
    assert await rated(viewer, comment, "like") == {"like_count": 1, "my_rating": "like"}

    assert mine(await comments_of(viewer, video)) == [(1, "like")]
    assert mine(await comments_of(owner, video)) == [(1, "none")]  # each viewer sees their own
    assert mine(await comments_of(guest, video)) == [(1, "none")]
    assert await stored(db, comment) == (1, [1])


async def test_reply_likes_count_on_the_reply(
    owner: AsyncClient, viewer: AsyncClient, video: Video, comment: str, db: AsyncSession
) -> None:
    reply = (await posted(owner, video, "Reply", comment))["id"]

    await rated(viewer, reply, "like")

    assert mine(await replies_to(viewer, comment)) == [(1, "like")]
    assert await stored(db, comment) == (0, [])


async def test_repeated_rating_counts_once_and_can_be_taken_back(
    viewer: AsyncClient, comment: str, db: AsyncSession
) -> None:
    for _ in range(3):
        assert await rated(viewer, comment, "like") == {"like_count": 1, "my_rating": "like"}

    assert await rated(viewer, comment, "dislike") == {"like_count": 0, "my_rating": "dislike"}
    assert await stored(db, comment) == (0, [-1])
    assert await rated(viewer, comment, "none") == {"like_count": 0, "my_rating": "none"}
    assert await stored(db, comment) == (0, [])


async def test_likes_move_a_comment_up_in_top(
    owner: AsyncClient, viewer: AsyncClient, video: Video
) -> None:
    older = (await posted(owner, video, "Older"))["id"]
    newer = (await posted(owner, video, "Newer"))["id"]

    top = await comments_of(viewer, video, "top")
    assert [item["id"] for item in top.json()["items"]] == [newer, older]  # a tie: newer first

    await rated(viewer, older, "like")

    top = await comments_of(viewer, video, "top")
    assert [item["id"] for item in top.json()["items"]] == [older, newer]


@pytest.mark.parametrize("body", [{"rating": "love"}, {}])
async def test_unknown_rating_is_refused(
    viewer: AsyncClient, comment: str, body: dict[str, object]
) -> None:
    response = await viewer.put(f"/api/comments/{comment}/rating", json=body, headers=csrf(viewer))

    assert response.status_code == 422


# --- Parallel requests ---


async def test_parallel_likes_of_many_users_all_count(
    make_viewers: MakeViewers,
    comment: str,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    viewers = await make_viewers(PARALLEL)

    meet_after(monkeypatch, comments_service, "get_readable", PARALLEL)
    responses = await asyncio.gather(*(rate(client, comment, "like") for client in viewers))

    assert [response.status_code for response in responses] == [200] * PARALLEL
    assert await stored(db, comment) == (PARALLEL, [1] * PARALLEL)


async def test_parallel_changes_of_one_user_keep_the_count_exact(
    viewer: AsyncClient, comment: str, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await rated(viewer, comment, "like")
    ratings = (["dislike", "none", "like"] * PARALLEL)[:PARALLEL]

    meet_after(monkeypatch, comments_service, "get_readable", PARALLEL)
    responses = await asyncio.gather(*(rate(viewer, comment, rating) for rating in ratings))

    assert [response.status_code for response in responses] == [200] * PARALLEL
    like_count, values = await stored(db, comment)
    assert like_count == values.count(1)  # whichever request came last
    assert len(values) <= 1


# --- Access ---


async def test_guest_cannot_rate(guest: AsyncClient, comment: str, db: AsyncSession) -> None:
    assert (await rate(guest, comment, "like")).status_code == 401
    assert await stored(db, comment) == (0, [])


async def test_rating_needs_the_csrf_token(viewer: AsyncClient, comment: str) -> None:
    response = await viewer.put(f"/api/comments/{comment}/rating", json={"rating": "like"})

    assert response.status_code == 403


async def test_unknown_comment_is_not_found(viewer: AsyncClient) -> None:
    assert (await rate(viewer, uuid4(), "like")).status_code == 404
    assert (await rate(viewer, "not-a-uuid", "like")).status_code == 422


async def test_comment_on_a_private_video_is_hidden_from_strangers(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    video = await make_video(
        db, await user_by_email(db, OWNER_EMAIL), visibility=Visibility.PRIVATE
    )
    comment = (await posted(owner, video, "Root"))["id"]

    stranger = await rate(viewer, comment, "like")
    assert stranger.status_code == 404
    assert stranger.json() == {"detail": "Comment not found"}  # same as for no comment at all

    await grant(db, video.public_id, VIEWER_EMAIL)
    assert await rated(viewer, comment, "like") == {"like_count": 1, "my_rating": "like"}
