"""Search (ADR 0007): Postgres full text over titles and descriptions, trigrams for title typos."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, decode_cursor, split_page
from app.modules.search.schemas import SearchResult
from app.modules.videos import repository as videos

PAGE_SIZE = 20


async def search(db: AsyncSession, words: str, cursor: str | None) -> Page[SearchResult]:
    after = decode_cursor(cursor, tuple[float, UUID]) if cursor else None
    rows = await videos.search(db, words, after=after, limit=PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, PAGE_SIZE, lambda row: (row[2], row[0].id))
    return Page(
        items=[SearchResult.of(video, owner) for video, owner, _ in page], next_cursor=next_cursor
    )
