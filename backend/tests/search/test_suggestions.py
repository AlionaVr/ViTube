"""GET /api/search/suggestions: titles of public videos close to what is typed."""

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.search.service import SUGGESTIONS
from app.modules.videos.models import VideoStatus, Visibility
from tests.videos.factories import make_user, make_video


async def suggestions(client: AsyncClient, typed: str) -> list[str]:
    response = await client.get("/api/search/suggestions", params={"q": typed})
    assert response.status_code == 200
    return response.json()


async def test_close_titles_come_closest_first_and_once(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await make_user(db, "owner")
    await make_video(db, owner, title="Sintel – trailer")
    await make_video(db, owner, title="Sintel – trailer")
    await make_video(db, owner, title="Sintel")
    await make_video(db, owner, title="Big Buck Bunny – trailer")

    assert await suggestions(client, "sintel") == ["Sintel", "Sintel – trailer"]


@pytest.mark.parametrize("typed", ["sin", "sintle"], ids=["start of a word", "typo"])
async def test_a_start_or_a_typo_is_enough(
    client: AsyncClient, db: AsyncSession, typed: str
) -> None:
    owner = await make_user(db, "owner")
    await make_video(db, owner, title="Sintel – trailer")
    await make_video(db, owner, title="Flower opening")

    assert await suggestions(client, typed) == ["Sintel – trailer"]


async def test_only_listed_titles_are_suggested(client: AsyncClient, db: AsyncSession) -> None:
    owner = await make_user(db, "owner")
    await make_video(db, owner, title="Dragon public")
    await make_video(db, owner, title="Dragon private", visibility=Visibility.PRIVATE)
    await make_video(db, owner, title="Dragon unlisted", visibility=Visibility.UNLISTED)
    await make_video(db, owner, title="Dragon draft", status=VideoStatus.UPLOADING)

    assert await suggestions(client, "dragon") == ["Dragon public"]


async def test_the_list_is_short(client: AsyncClient, db: AsyncSession) -> None:
    owner = await make_user(db, "owner")
    for n in range(SUGGESTIONS + 2):
        await make_video(db, owner, title=f"Dragon {n}")

    assert len(await suggestions(client, "dragon")) == SUGGESTIONS


async def test_what_is_typed_is_checked(client: AsyncClient) -> None:
    response = await client.get("/api/search/suggestions", params={"q": "  "})

    assert response.status_code == 422
