"""Comments and replies: writing, threads, pages, parallel posts, access."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.modules.comments import repository, service
from app.modules.comments.models import TEXT_MAX, Comment
from app.modules.users.models import User
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.interactions.conftest import (
    OWNER_EMAIL,
    VIEWER_EMAIL,
    MakeViewers,
    comments_of,
    ids,
    meet_after,
    post,
    posted,
    replies_to,
    user_by_email,
)
from tests.videos.factories import get_video, grant, make_video

NOT_READY = [status for status in VideoStatus if status is not VideoStatus.READY]
PAGE = service.PAGE_SIZE
PARALLEL = 10


async def comment_count(db: AsyncSession, video: Video) -> int:
    return (await get_video(db, video.public_id)).comment_count


async def reply_count(db: AsyncSession, comment_id: object) -> int:
    query = select(Comment.reply_count).where(Comment.id == UUID(str(comment_id)))
    return (await db.execute(query)).scalar_one()


async def add_comments(
    db: AsyncSession,
    video: Video,
    author: User,
    count: int,
    parent_id: UUID | None = None,
    likes: Callable[[int], int] = lambda _: 0,
) -> list[Comment]:
    """Comments straight in the DB: pages need more of them than the API would make quickly."""
    rows = [
        Comment(
            video_id=video.id,
            author_id=author.id,
            parent_id=parent_id,
            text=f"Comment {number}",
            like_count=likes(number),
        )
        for number in range(count)
    ]
    db.add_all(rows)
    await db.commit()
    return rows


async def all_pages(fetch: Callable[[str | None], Awaitable[Response]]) -> list[str]:
    """Follow next_cursor to the end; returns the ids in the order the pages gave them."""
    seen: list[str] = []
    cursor = None
    while True:
        response = await fetch(cursor)
        seen += ids(response)
        cursor = response.json()["next_cursor"]
        if cursor is None:
            return seen


# --- Writing and reading ---


async def test_comment_is_posted_and_listed(
    viewer: AsyncClient, guest: AsyncClient, video: Video, db: AsyncSession
) -> None:
    comment = await posted(viewer, video, "  First!  ")

    handle = (await viewer.get("/api/auth/me")).json()["handle"]
    assert comment["text"] == "First!"
    assert comment["author"] == {"handle": handle, "name": handle, "avatar_url": None}
    assert (comment["by_owner"], comment["like_count"], comment["reply_count"]) == (False, 0, 0)
    listed = (await comments_of(guest, video)).json()
    assert listed == {"items": [comment], "next_cursor": None}
    assert await comment_count(db, video) == 1


async def test_owner_comment_is_marked(owner: AsyncClient, video: Video) -> None:
    assert (await posted(owner, video))["by_owner"] is True


async def test_guest_reads_but_cannot_write(
    guest: AsyncClient, video: Video, db: AsyncSession
) -> None:
    assert (await post(guest, video)).status_code == 401
    assert (await comments_of(guest, video)).status_code == 200
    assert await comment_count(db, video) == 0


@pytest.mark.parametrize(
    "text",
    ["", "  \n\t ", "x" * (TEXT_MAX + 1), "a\x00b", "a\x1b[31mred"],
    ids=["empty", "blank", "too-long", "nul", "terminal-escape"],
)
async def test_bad_text_is_refused(
    viewer: AsyncClient, video: Video, db: AsyncSession, text: str
) -> None:
    assert (await post(viewer, video, text)).status_code == 422
    assert await comment_count(db, video) == 0


async def test_longest_text_is_taken(viewer: AsyncClient, video: Video) -> None:
    assert (await post(viewer, video, "x" * TEXT_MAX)).status_code == 201


async def test_tabs_and_newlines_are_kept(viewer: AsyncClient, video: Video) -> None:
    text = "Line one\n\tline two\r\nend"

    assert (await posted(viewer, video, f"  {text}  "))["text"] == text


async def test_comment_needs_the_csrf_token(viewer: AsyncClient, video: Video) -> None:
    response = await viewer.post(f"/api/videos/{video.public_id}/comments", json={"text": "Hi"})

    assert response.status_code == 403


# --- Replies ---


async def test_reply_to_a_reply_joins_the_thread(
    owner: AsyncClient, viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    root = await posted(owner, video, "Root")
    reply = await posted(viewer, video, "Reply", root["id"])
    reply_to_reply = await posted(owner, video, "Reply to the reply", reply["id"])

    assert ids(await replies_to(viewer, root["id"])) == [reply["id"], reply_to_reply["id"]]
    assert ids(await replies_to(viewer, reply["id"])) == []
    top = (await comments_of(viewer, video)).json()["items"]
    assert [(item["id"], item["reply_count"]) for item in top] == [(root["id"], 2)]
    assert await comment_count(db, video) == 3  # replies count too, as on YouTube


async def test_parent_must_be_a_comment_of_the_same_video(
    owner: AsyncClient, viewer: AsyncClient, video: Video, db: AsyncSession
) -> None:
    other_video = await make_video(db, await user_by_email(db, OWNER_EMAIL))
    elsewhere = await posted(owner, other_video, "On another video")

    for parent_id in (elsewhere["id"], uuid4()):
        response = await post(viewer, video, "Reply", parent_id)
        assert response.status_code == 404
        assert response.json() == {"detail": "Comment not found"}
    assert await comment_count(db, video) == 0
    assert await reply_count(db, elsewhere["id"]) == 0


# --- Order and pages ---


async def test_newest_first(viewer: AsyncClient, video: Video) -> None:
    first, second, third = [(await posted(viewer, video, text))["id"] for text in "abc"]

    assert ids(await comments_of(viewer, video, "new")) == [third, second, first]


async def test_most_liked_first_then_newest(
    owner: AsyncClient, video: Video, db: AsyncSession
) -> None:
    owner_user = await user_by_email(db, OWNER_EMAIL)
    first, second, third = await add_comments(db, video, owner_user, 3, likes=[5, 0, 5].__getitem__)

    assert ids(await comments_of(owner, video, "top")) == [
        str(third.id),
        str(first.id),
        str(second.id),
    ]


@pytest.mark.parametrize("sort", ["top", "new"])
async def test_pages_give_every_comment_once(
    owner: AsyncClient, video: Video, db: AsyncSession, sort: str
) -> None:
    owner_user = await user_by_email(db, OWNER_EMAIL)
    # Ties in likes across page borders: the id breaks them.
    rows = await add_comments(db, video, owner_user, 2 * PAGE + 5, likes=lambda n: n % 3)
    if sort == "top":
        expected = sorted(rows, key=lambda row: (row.like_count, row.id), reverse=True)
    else:
        expected = sorted(rows, key=lambda row: row.id, reverse=True)

    seen = await all_pages(lambda cursor: comments_of(owner, video, sort, cursor))

    assert seen == [str(row.id) for row in expected]


async def test_new_comments_do_not_shift_the_next_page(
    owner: AsyncClient, video: Video, db: AsyncSession
) -> None:
    owner_user = await user_by_email(db, OWNER_EMAIL)
    rows = await add_comments(db, video, owner_user, PAGE + 5)
    first_page = (await comments_of(owner, video, "new")).json()

    await add_comments(db, video, owner_user, 3)  # with OFFSET, page 2 would repeat 3 comments
    second_page = await comments_of(owner, video, "new", first_page["next_cursor"])

    seen = [item["id"] for item in first_page["items"]] + ids(second_page)
    assert seen == [str(row.id) for row in sorted(rows, key=lambda row: row.id, reverse=True)]


async def test_replies_come_oldest_first_in_pages(
    owner: AsyncClient, video: Video, db: AsyncSession
) -> None:
    owner_user = await user_by_email(db, OWNER_EMAIL)
    [root] = await add_comments(db, video, owner_user, 1)
    replies = await add_comments(db, video, owner_user, PAGE + 5, parent_id=root.id)

    seen = await all_pages(lambda cursor: replies_to(owner, root.id, cursor))

    assert seen == [str(row.id) for row in sorted(replies, key=lambda row: row.id)]


async def test_bad_cursor_is_refused(viewer: AsyncClient, video: Video, db: AsyncSession) -> None:
    owner_user = await user_by_email(db, OWNER_EMAIL)
    await add_comments(db, video, owner_user, PAGE + 1)
    new_cursor = (await comments_of(viewer, video, "new")).json()["next_cursor"]

    assert (await comments_of(viewer, video, "new", "garbage")).status_code == 400
    assert (await comments_of(viewer, video, "top", new_cursor)).status_code == 400


@pytest.mark.parametrize("like_count", [-1, 2**31, 2**63])
async def test_cursor_out_of_the_column_range_is_refused(
    viewer: AsyncClient, video: Video, like_count: int
) -> None:
    cursor = encode_cursor((like_count, uuid4()))

    response = await comments_of(viewer, video, "top", cursor)

    assert response.status_code == 400  # not a DB error


async def test_only_thread_roots_count_replies(
    owner: AsyncClient, video: Video, db: AsyncSession
) -> None:
    owner_user = await user_by_email(db, OWNER_EMAIL)
    [root] = await add_comments(db, video, owner_user, 1)
    [reply] = await add_comments(db, video, owner_user, 1, parent_id=root.id)

    with pytest.raises(IntegrityError, match="only_roots_have_replies"):
        await db.execute(update(Comment).where(Comment.id == reply.id).values(reply_count=1))
    await db.rollback()


# --- Parallel posts ---


def skipped(seen: list[str], every: list[str]) -> list[str]:
    """Comments a reader paging by id never gets: unseen, yet inside the id range it has read."""
    if not seen:
        return []
    low, high = min(map(UUID, seen)), max(map(UUID, seen))
    return [id_ for id_ in every if id_ not in seen and low < UUID(id_) < high]


@pytest.mark.parametrize("thread", [True, False], ids=["replies", "newest-first"])
async def test_a_post_that_commits_later_is_not_skipped(
    owner: AsyncClient,
    make_viewers: MakeViewers,
    video: Video,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    thread: bool,
) -> None:
    """The race: A gets its id, then waits; B gets a later id and commits first. A reader sees B,
    moves its cursor past A's id, and A, committed later, is behind it for good."""
    root = str((await posted(owner, video, "Root"))["id"]) if thread else None
    await posted(owner, video, "Older", root)  # so A falls inside what the reader has seen
    a_client, b_client = await make_viewers(2)
    a_author = (await user_by_email(db, "user0@example.com")).id

    async def read() -> list[str]:
        return ids(await (replies_to(owner, root) if thread else comments_of(owner, video, "new")))

    a_inserted, resume_a = asyncio.Event(), asyncio.Event()
    insert = repository.insert_comment

    async def insert_then_pause(
        session: AsyncSession, *, video_id: UUID, author_id: UUID, parent_id: UUID | None, text: str
    ) -> Comment:
        comment = await insert(
            session, video_id=video_id, author_id=author_id, parent_id=parent_id, text=text
        )
        if author_id == a_author:
            a_inserted.set()
            await resume_a.wait()  # A keeps every lock it has taken so far
        return comment

    monkeypatch.setattr(repository, "insert_comment", insert_then_pause)
    a = asyncio.create_task(post(a_client, video, "A", root))
    await asyncio.wait_for(a_inserted.wait(), 5)
    b = asyncio.create_task(post(b_client, video, "B", root))
    await asyncio.wait({b}, timeout=0.5)  # B commits now, unless it has to wait for A's locks
    seen = await read()
    resume_a.set()

    assert [response.status_code for response in await asyncio.gather(a, b)] == [201, 201]
    assert skipped(seen, await read()) == []


@pytest.mark.parametrize("thread", [True, False], ids=["replies", "newest-first"])
async def test_readers_during_parallel_posts_see_commit_order(
    app: FastAPI,
    owner: AsyncClient,
    make_viewers: MakeViewers,
    video: Video,
    monkeypatch: pytest.MonkeyPatch,
    thread: bool,
) -> None:
    """Each read while posts run must be the start of the final list (its end, newest first):
    ids follow commit order, checked rather than assumed."""
    root = str((await posted(owner, video, "Root"))["id"]) if thread else None
    viewers = await make_viewers(PARALLEL)
    posting = asyncio.Event()
    snapshots: list[list[str]] = []

    async def read(session: AsyncSession) -> list[str]:
        # The repository query itself: the API route would also hit the writers' barrier.
        if root is not None:
            rows = await repository.list_replies(session, UUID(root), after=None, limit=100)
        else:
            rows = await repository.list_newest(session, video.id, before=None, limit=100)
        return [str(comment.id) for comment, _ in rows]

    async def watch() -> None:
        async with app.state.sessionmaker() as session:
            while posting.is_set():
                snapshots.append(await read(session))
                await session.rollback()  # a new transaction, a fresh view, each time

    meet_after(monkeypatch, service, "get_ready", PARALLEL)
    posting.set()
    watcher = asyncio.create_task(watch())
    responses = await asyncio.gather(*(post(client, video, "Hi", root) for client in viewers))
    posting.clear()
    await watcher

    assert [response.status_code for response in responses] == [201] * PARALLEL
    async with app.state.sessionmaker() as session:
        every = await read(session)
    assert len(snapshots) > 1
    for seen in snapshots:
        assert seen == (every[: len(seen)] if thread else every[len(every) - len(seen) :])


async def test_parallel_posts_keep_the_counts_exact(
    owner: AsyncClient,
    make_viewers: MakeViewers,
    video: Video,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = await posted(owner, video, "Root")
    viewers = await make_viewers(PARALLEL)
    # Half reply to the root, half comment on the video.
    parents = [root["id"] if number % 2 else None for number in range(PARALLEL)]

    meet_after(monkeypatch, service, "get_ready", PARALLEL)
    responses = await asyncio.gather(
        *(
            post(client, video, "Hi", parent)
            for client, parent in zip(viewers, parents, strict=True)
        )
    )

    assert [response.status_code for response in responses] == [201] * PARALLEL
    assert await reply_count(db, root["id"]) == PARALLEL // 2
    assert await comment_count(db, video) == 1 + PARALLEL


# --- Access ---


async def test_private_video_comments_are_hidden_from_strangers(
    owner: AsyncClient, viewer: AsyncClient, db: AsyncSession
) -> None:
    video = await make_video(
        db, await user_by_email(db, OWNER_EMAIL), visibility=Visibility.PRIVATE
    )
    root = await posted(owner, video, "Root")

    assert (await comments_of(viewer, video)).status_code == 404
    assert (await post(viewer, video)).status_code == 404
    hidden = await replies_to(viewer, root["id"])
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Comment not found"}  # same as for no comment at all

    await grant(db, video.public_id, VIEWER_EMAIL)
    assert ids(await comments_of(viewer, video)) == [root["id"]]
    assert ids(await replies_to(viewer, root["id"])) == []
    assert (await post(viewer, video, "Reply", root["id"])).status_code == 201


@pytest.mark.parametrize("status", NOT_READY)
async def test_unfinished_video_takes_no_comments_even_from_its_owner(
    owner: AsyncClient, db: AsyncSession, status: VideoStatus
) -> None:
    video = await make_video(db, await user_by_email(db, OWNER_EMAIL), status=status)

    assert (await comments_of(owner, video)).status_code == 404
    assert (await post(owner, video)).status_code == 404


async def test_unknown_comment_has_no_replies(viewer: AsyncClient) -> None:
    assert (await replies_to(viewer, uuid4())).status_code == 404
    assert (await replies_to(viewer, "not-a-uuid")).status_code == 422
