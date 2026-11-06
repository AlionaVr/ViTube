from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Separate from Settings: only the api reads them, so only the api gets the secret."""

    session_secret: SecretStr = Field(min_length=32)  # refuses "change-me" from .env.example


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()  # pyright: ignore[reportCallIssue]
