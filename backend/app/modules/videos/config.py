import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

MIB = 1024 * 1024


class VideoSettings(BaseSettings):
    """Upload limits (ADR 0006) and worker settings, from env; README lists the limits."""

    max_upload_size_mb: int = Field(default=1024, gt=0)
    max_video_duration_sec: int = Field(default=1800, gt=0)
    max_video_height: int = Field(default=720, gt=0)  # taller videos are downscaled
    scratch_dir: Path = Path(tempfile.gettempdir())  # the worker's work files (a volume in compose)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * MIB  # MiB, like nginx's client_max_body_size "m"


@lru_cache
def get_video_settings() -> VideoSettings:
    return VideoSettings()
