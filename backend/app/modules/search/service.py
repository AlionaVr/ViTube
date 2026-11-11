"""Search (ADR 0007): Postgres full text over titles and descriptions, trigrams for title typos."""

import re
from uuid import UUID

from pydantic import FiniteFloat
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, decode_cursor, split_page
from app.core.rate_limit import RateLimit
from app.modules.search.schemas import SearchResult
from app.modules.videos import repository as videos

PAGE_SIZE = 20
SUGGESTIONS = 10
# Guests search too, and each search reads many rows: a budget per IP. Pages count as searches.
SEARCHES_PER_IP = RateLimit("search_ip", limit=60, window=60)
# The box asks in every pause in typing.
SUGGESTIONS_PER_IP = RateLimit("suggest_ip", limit=300, window=60)
# Shorter input matches a large share of titles by trigrams: slow and of no use.
TYPO_MIN_CHARS = 3
SUGGEST_MIN_CHARS = 2
# "-word" excludes; a typo match on the title would bring the word back.
NEGATION = re.compile(r"(?:^|\s)-\S")


def _chars(words: str) -> int:
    """Letters and digits: punctuation alone gives no trigrams to look up."""
    return sum(char.isalnum() for char in words)


async def search(
    db: AsyncSession, redis: Redis, ip: str, words: str, cursor: str | None
) -> Page[SearchResult]:
    await SEARCHES_PER_IP.hit(redis, ip)
    after = decode_cursor(cursor, tuple[FiniteFloat, UUID]) if cursor else None
    typos = _chars(words) >= TYPO_MIN_CHARS and not NEGATION.search(words)
    rows = await videos.search(db, words, typos=typos, after=after, limit=PAGE_SIZE + 1)
    page, next_cursor = split_page(rows, PAGE_SIZE, lambda row: (row[2], row[0].id))
    return Page(
        items=[SearchResult.of(video, owner) for video, owner, _ in page], next_cursor=next_cursor
    )


async def suggest(db: AsyncSession, redis: Redis, ip: str, words: str) -> list[str]:
    await SUGGESTIONS_PER_IP.hit(redis, ip)
    if _chars(words) < SUGGEST_MIN_CHARS:
        return []
    return await videos.suggest_titles(db, words, limit=SUGGESTIONS)
