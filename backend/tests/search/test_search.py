"""GET /api/search: full text over titles and descriptions, title typos, listed videos only."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.service import PAGE_SIZE
from app.modules.users.models import User
from app.modules.videos.models import Video, VideoStatus, Visibility
from tests.videos.factories import make_user, make_video

SINTEL = "Sintel – trailer"
DRAGON = "A lone girl searches for the baby dragon she once saved."


async def found(client: AsyncClient, words: str) -> list[str]:
    """Follow next_cursor to the end; the titles in the order the pages gave them."""
    titles: list[str] = []
    cursor = None
    while True:
        params = {"q": words} | ({"cursor": cursor} if cursor else {})
        response = await client.get("/api/search", params=params)
        assert response.status_code == 200
        titles += [item["title"] for item in response.json()["items"]]
        cursor = response.json()["next_cursor"]
        if cursor is None:
            return titles


@pytest.fixture
async def owner(db: AsyncSession) -> User:
    return await make_user(db, "owner")


async def test_a_result_shows_the_video_its_channel_and_description(
    client: AsyncClient, db: AsyncSession, owner: User
) -> None:
    video = await make_video(db, owner, title=SINTEL, description=DRAGON)

    response = await client.get("/api/search", params={"q": "sintel"})

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["id"] == video.public_id
    assert item["description"] == DRAGON
    assert item["channel"] == {"handle": "owner", "name": "owner", "avatar_url": None}
    assert item["thumbnail_url"] == f"/media/thumbs/{video.id}.jpg"


async def test_a_title_match_ranks_above_a_description_match(
    client: AsyncClient, db: AsyncSession, owner: User
) -> None:
    await make_video(db, owner, title="Night flight", description="A dragon over the sea.")
    await make_video(db, owner, title="Dragon notes")
    await make_video(db, owner, title="Unrelated")

    assert await found(client, "dragon") == ["Dragon notes", "Night flight"]


async def test_other_word_forms_match(client: AsyncClient, db: AsyncSession, owner: User) -> None:
    await make_video(db, owner, title=SINTEL)

    assert await found(client, "trailers") == [SINTEL]


@pytest.mark.parametrize("typo", ["sintle", "trailr", "SINTEL TRAILR"])
async def test_a_typo_in_the_title_still_finds_it(
    client: AsyncClient, db: AsyncSession, owner: User, typo: str
) -> None:
    await make_video(db, owner, title=SINTEL)
    await make_video(db, owner, title="Concatenate strings in Python")

    assert await found(client, typo) == [SINTEL]


async def test_only_listed_videos_are_found(
    client: AsyncClient, db: AsyncSession, owner: User
) -> None:
    await make_video(db, owner, title="Dragon public")
    await make_video(db, owner, title="Dragon unlisted", visibility=Visibility.UNLISTED)
    await make_video(db, owner, title="Dragon private", visibility=Visibility.PRIVATE)
    await make_video(db, owner, title="Dragon processing", status=VideoStatus.PROCESSING)

    assert await found(client, "dragon") == ["Dragon public"]


async def test_an_edited_title_is_searched_at_once(
    client: AsyncClient, db: AsyncSession, owner: User
) -> None:
    video = await make_video(db, owner, title="Old name")
    video.title = "Dragon notes"
    await db.commit()

    assert await found(client, "dragon") == ["Dragon notes"]


async def test_pages_go_by_rank_without_gaps_or_repeats(
    client: AsyncClient, db: AsyncSession, owner: User
) -> None:
    # Equal ranks on a page border: the id breaks the tie.
    made: list[Video] = [
        await make_video(db, owner, title=f"Dragon {n}") for n in range(PAGE_SIZE + 3)
    ]
    await make_video(db, owner, title="Dragon", description="Dragon dragon")

    titles = await found(client, "dragon")

    assert titles[0] == "Dragon"
    assert sorted(titles[1:]) == sorted(video.title for video in made)
    assert len(titles) == len(set(titles))


@pytest.mark.parametrize(
    "params",
    [{}, {"q": ""}, {"q": "   "}, {"q": "x" * 201}],
    ids=["none", "empty", "blank", "long"],
)
async def test_the_query_is_checked(client: AsyncClient, params: dict[str, str]) -> None:
    response = await client.get("/api/search", params=params)

    assert response.status_code == 422


async def test_a_bad_cursor_is_refused(client: AsyncClient) -> None:
    response = await client.get("/api/search", params={"q": "dragon", "cursor": "not-a-cursor"})

    assert response.status_code == 400


async def test_words_that_match_nothing_give_an_empty_page(
    client: AsyncClient, db: AsyncSession, owner: User
) -> None:
    await make_video(db, owner, title=SINTEL)

    response = await client.get("/api/search", params={"q": "the"})  # a stop word, no lexemes

    assert response.json() == {"items": [], "next_cursor": None}
