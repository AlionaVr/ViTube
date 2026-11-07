from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings

MIB = 1024 * 1024


class VideoSettings(BaseSettings):
    """Upload limits (ADR 0006), from env; README lists them."""

    max_upload_size_mb: int = Field(default=1024, gt=0)
    max_video_duration_sec: int = Field(default=1800, gt=0)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * MIB  # MiB, like nginx's client_max_body_size "m"


@lru_cache
def get_video_settings() -> VideoSettings:
    return VideoSettings()
