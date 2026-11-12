from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Separate from Settings: only the api reads them, so only the api gets the secret."""

    session_secret: SecretStr = Field(min_length=32)  # refuses "change-me" from .env.example
    cookie_secure: bool = False  # true behind HTTPS; plain HTTP (a VM by IP) needs false
    # Sign-in with Google (ADR 0014): off while the client id is empty.
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    # The web app's callback page; must be an authorized redirect URI of the Google client.
    google_redirect_uri: str = "http://localhost/auth/google/callback"

    @model_validator(mode="after")
    def _google_secret_with_id(self) -> Self:
        if self.google_client_id and not self.google_client_secret.get_secret_value():
            raise ValueError("GOOGLE_CLIENT_SECRET is required with GOOGLE_CLIENT_ID")
        return self


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()  # pyright: ignore[reportCallIssue]
