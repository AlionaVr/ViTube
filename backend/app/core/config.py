from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings. Values come from environment variables (names are case-insensitive)."""

    database_url: PostgresDsn
    redis_url: RedisDsn


@lru_cache
def get_settings() -> Settings:
    # Built on first use, so importing a module never requires env vars.
    # pyright can't see that pydantic-settings fills the fields from env.
    return Settings()  # pyright: ignore[reportCallIssue]
