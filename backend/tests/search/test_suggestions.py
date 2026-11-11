"""GET /api/search/suggestions: titles of public videos close to what is typed."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.modules.search import service
from app.modules.search.service import SUGGESTIONS
from app.modules.videos.models import VideoStatus, Visibility
from tests.videos.factories import make_user, make_video


async def suggestions(client: AsyncClient, typed: str) -> list[str]:
    response = await client.get("/api/search/suggestions", params={"q": typed})
    assert response.status_code == 200
    return response.json()


async def test_close_titles_come_closest_first_once_and_in_lower_case(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await make_user(db, "owner")
    await make_video(db, owner, title="Sintel – trailer")
    await make_video(db, owner, title="SINTEL – Trailer")
    await make_video(db, owner, title="Sintel")
    await make_video(db, owner, title="Big Buck Bunny – trailer")

    # Lower case, like YouTube's suggestions: titles that differ only in case come once.
    assert await suggestions(client, "sintel") == ["sintel", "sintel – trailer"]


@pytest.mark.parametrize("typed", ["sin", "sintle"], ids=["start of a word", "typo"])
async def test_a_start_or_a_typo_is_enough(
    client: AsyncClient, db: AsyncSession, typed: str
) -> None:
    owner = await make_user(db, "owner")
    await make_video(db, owner, title="Sintel – trailer")
    await make_video(db, owner, title="Flower opening")

    assert await suggestions(client, typed) == ["sintel – trailer"]


async def test_only_listed_titles_are_suggested(client: AsyncClient, db: AsyncSession) -> None:
    owner = await make_user(db, "owner")
    await make_video(db, owner, title="Dragon public")
    await make_video(db, owner, title="Dragon private", visibility=Visibility.PRIVATE)
    await make_video(db, owner, title="Dragon unlisted", visibility=Visibility.UNLISTED)
    await make_video(db, owner, title="Dragon draft", status=VideoStatus.UPLOADING)

    assert await suggestions(client, "dragon") == ["dragon public"]


async def test_the_list_is_short(client: AsyncClient, db: AsyncSession) -> None:
    owner = await make_user(db, "owner")
    for n in range(SUGGESTIONS + 2):
        await make_video(db, owner, title=f"Dragon {n}")

    assert len(await suggestions(client, "dragon")) == SUGGESTIONS


@pytest.mark.parametrize("typed", ["  ", "a\x00"], ids=["blank", "NUL"])
async def test_what_is_typed_is_checked(client: AsyncClient, typed: str) -> None:
    response = await client.get("/api/search/suggestions", params={"q": typed})

    assert response.status_code == 422


@pytest.mark.parametrize("typed", ["s", "s!", "—"])
async def test_one_letter_or_punctuation_suggests_nothing(
    client: AsyncClient, db: AsyncSession, typed: str
) -> None:
    await make_video(db, await make_user(db, "owner"), title="Sintel – trailer")

    assert await suggestions(client, typed) == []


async def test_suggestions_are_limited_per_ip(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit = RateLimit("suggest_ip", limit=2, window=60)
    monkeypatch.setattr(service, "SUGGESTIONS_PER_IP", limit)
    for _ in range(2):
        await suggestions(client, "dragon")

    response = await client.get("/api/search/suggestions", params={"q": "dragon"})

    assert response.status_code == 429
