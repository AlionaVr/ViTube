"""/api/search: public videos by words. Guests search too."""

from fastapi import APIRouter, Request

from app.core.pagination import Cursor, Page
from app.core.rate_limit import client_ip
from app.core.redis import RedisClient
from app.db.session import DbSession
from app.modules.search import service
from app.modules.search.schemas import SearchQuery, SearchResult

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=Page[SearchResult], summary="Search public videos, best match first")
async def search(
    request: Request, db: DbSession, redis: RedisClient, q: SearchQuery, cursor: Cursor = None
) -> Page[SearchResult]:
    return await service.search(db, redis, client_ip(request), q, cursor)


@router.get(
    "/suggestions",
    response_model=list[str],
    summary="Titles of public videos close to what is typed, closest first, in lower case",
)
async def suggest(request: Request, db: DbSession, redis: RedisClient, q: SearchQuery) -> list[str]:
    return await service.suggest(db, redis, client_ip(request), q)
