"""Streaming uploads to MinIO: parts, abort on errors and cancellation."""

import uuid
from collections.abc import AsyncIterator
from functools import partial

import anyio
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from types_aiobotocore_s3 import S3Client

from app.core.storage import PART_SIZE, Storage, get_storage_settings, open_s3_client

MIB = 1024 * 1024


@pytest.fixture
def storage(app: FastAPI) -> Storage:
    return app.state.storage


@pytest.fixture
async def s3(app: FastAPI) -> AsyncIterator[S3Client]:
    """A raw client to look at the bucket."""
    async with open_s3_client(get_storage_settings()) as client:
        yield client


def new_key() -> str:
    return f"test/{uuid.uuid4()}"


async def chunks_of(*sizes: int) -> AsyncIterator[bytes]:
    for number, size in enumerate(sizes):
        yield bytes([number % 256]) * size


async def read(s3: S3Client, key: str) -> bytes:
    response = await s3.get_object(Bucket=get_storage_settings().s3_bucket, Key=key)
    async with response["Body"] as body:
        return await body.read()


async def assert_nothing_stored(s3: S3Client, key: str) -> None:
    bucket = get_storage_settings().s3_bucket
    with pytest.raises(ClientError, match="404"):
        await s3.head_object(Bucket=bucket, Key=key)
    uploads = await s3.list_multipart_uploads(Bucket=bucket, Prefix=key)
    assert uploads.get("Uploads", []) == []


async def test_small_upload_is_one_object(storage: Storage, s3: S3Client) -> None:
    key = new_key()

    size = await storage.upload(key, chunks_of(10, 20), content_type="video/mp4")

    assert size == 30
    assert await read(s3, key) == b"\x00" * 10 + b"\x01" * 20
    head = await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=key)
    assert head["ContentType"] == "video/mp4"


async def test_large_upload_goes_in_parts(storage: Storage, s3: S3Client) -> None:
    key = new_key()
    sizes = [MIB] * (PART_SIZE // MIB + 1)  # one byte past a part: two parts

    size = await storage.upload(key, chunks_of(*sizes), content_type="video/mp4")

    assert size == sum(sizes)
    assert await read(s3, key) == b"".join([bytes([n]) * MIB for n in range(len(sizes))])
    head = await s3.head_object(Bucket=get_storage_settings().s3_bucket, Key=key)
    assert head["ETag"].endswith('-2"')  # a multipart ETag ends with the part count


async def test_empty_stream_stores_an_empty_object(storage: Storage, s3: S3Client) -> None:
    key = new_key()

    assert await storage.upload(key, chunks_of(), content_type="video/mp4") == 0
    assert await read(s3, key) == b""


async def test_an_error_mid_stream_stores_nothing(storage: Storage, s3: S3Client) -> None:
    key = new_key()

    async def broken() -> AsyncIterator[bytes]:
        yield b"x" * PART_SIZE  # one part is already in MinIO
        raise ConnectionResetError("client went away")

    with pytest.raises(ConnectionResetError):
        await storage.upload(key, broken(), content_type="video/mp4")

    await assert_nothing_stored(s3, key)


async def test_a_cancelled_upload_stores_nothing(storage: Storage, s3: S3Client) -> None:
    key = new_key()
    first_part_sent = anyio.Event()

    async def stalled() -> AsyncIterator[bytes]:
        yield b"x" * PART_SIZE
        yield b"y"  # the first part goes out while this one waits in the buffer
        first_part_sent.set()
        await anyio.sleep_forever()
        yield b""  # pragma: no cover

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(partial(storage.upload, key, stalled(), content_type="video/mp4"))
        await first_part_sent.wait()
        tasks.cancel_scope.cancel()  # e.g. the server stops the request

    await assert_nothing_stored(s3, key)
