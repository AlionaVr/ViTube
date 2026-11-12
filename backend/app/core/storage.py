"""Object storage: MinIO over the S3 API (ADR 0002). AWS S3 or any S3 server works via config."""

import logging
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import anyio
from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from fastapi import Depends, Request
from pydantic import SecretStr
from pydantic_settings import BaseSettings

if TYPE_CHECKING:  # stubs are a dev dependency
    from types_aiobotocore_s3 import S3Client
    from types_aiobotocore_s3.type_defs import CompletedPartTypeDef

log = logging.getLogger(__name__)

# S3 parts must be at least 5 MiB, except the last one. An upload holds one part in memory.
PART_SIZE = 8 * 1024 * 1024
FILE_CHUNK = 1024 * 1024


class StorageSettings(BaseSettings):
    """Only api, worker and seed read them, so only they get the storage secret."""

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_bucket: str


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()  # pyright: ignore[reportCallIssue]


class Storage:
    def __init__(self, client: "S3Client", bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def upload(self, key: str, chunks: AsyncIterable[bytes], *, content_type: str) -> int:
        """Stream chunks into an object, part by part. Returns the size in bytes.

        The object appears only if the stream ends normally. On any error, a cancellation or a
        cut-off client, the upload is aborted and the error goes on.
        """
        created = await self._client.create_multipart_upload(
            Bucket=self._bucket, Key=key, ContentType=content_type
        )
        upload_id = created["UploadId"]
        parts: list[CompletedPartTypeDef] = []  # local annotation: never evaluated
        buffer = bytearray()
        size = 0

        async def send_part() -> None:
            number = len(parts) + 1
            sent = await self._client.upload_part(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=number,
                Body=bytes(buffer),
            )
            parts.append({"PartNumber": number, "ETag": sent["ETag"]})
            buffer.clear()

        try:
            async for chunk in chunks:
                size += len(chunk)
                buffer += chunk
                if len(buffer) >= PART_SIZE:
                    await send_part()
            if buffer or not parts:  # the last part; an empty object still needs one
                await send_part()
            await self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except BaseException:
            await self._abort(key, upload_id)
            raise
        return size

    async def upload_file(self, key: str, path: Path, *, content_type: str) -> int:
        return await self.upload(key, read_chunks(path), content_type=content_type)

    async def download(self, key: str, path: Path) -> None:
        """Stream an object into a local file."""
        response = await self._client.get_object(Bucket=self._bucket, Key=key)
        async with response["Body"] as body, await anyio.open_file(path, "wb") as file:
            async for chunk in body.iter_chunks(FILE_CHUNK):
                await file.write(chunk)

    async def _abort(self, key: str, upload_id: str) -> None:
        # Shielded: a cancelled request must still drop its parts.
        with anyio.CancelScope(shield=True):
            try:
                await self._client.abort_multipart_upload(
                    Bucket=self._bucket, Key=key, UploadId=upload_id
                )
            except Exception:
                # The first error matters more; MinIO drops stale parts itself after a day.
                log.exception("Could not abort the upload of %s", key)


async def read_chunks(path: Path) -> AsyncIterator[bytes]:
    async with await anyio.open_file(path, "rb") as file:
        while chunk := await file.read(FILE_CHUNK):
            yield chunk


@asynccontextmanager
async def open_s3_client(settings: StorageSettings) -> AsyncIterator["S3Client"]:
    """An S3 client with its own connection pool."""
    config = AioConfig(
        s3={"addressing_style": "path"},  # MinIO: bucket in the path, not in the host name
        connect_timeout=5,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    client_context = get_session().create_client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name="us-east-1",  # MinIO's default; S3 signatures need one
        config=config,
    )
    async with client_context as client:
        yield client


@asynccontextmanager
async def open_storage(settings: StorageSettings) -> AsyncIterator[Storage]:
    """Storage for the app's lifetime (api) or one job (worker), like a singleton bean."""
    async with open_s3_client(settings) as client:
        yield Storage(client, settings.s3_bucket)


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


StorageClient = Annotated[Storage, Depends(get_storage)]
