from fastapi import Request
from redis.asyncio import Redis

from app.core.config import Settings


def create_redis(settings: Settings) -> Redis:
    # decode_responses: values come back as str, not bytes.
    return Redis.from_url(str(settings.redis_url), decode_responses=True)


def get_redis(request: Request) -> Redis:
    return request.app.state.redis
