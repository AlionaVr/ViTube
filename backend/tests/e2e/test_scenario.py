"""End to end on a running stack, through nginx: upload → processing → playback, with access rules.

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
Accounts are reused between runs (login, else sign up), so reruns don't hit the sign-up limit.
"""

import json
import os
import secrets
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx2 import Client, Response

BASE_URL = os.environ.get("E2E_BASE_URL", "")
PASSWORD = "e2e correct horse battery"
PROCESSING_TIMEOUT_SEC = 180

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")


class Browser:
    """A browser's view of the site: its own cookies, Origin and CSRF header like the web app."""

    def __init__(self) -> None:
        self.http = Client(base_url=BASE_URL, headers={"Origin": BASE_URL}, timeout=60)

    def _csrf(self) -> dict[str, str]:
        token = self.http.cookies.get("csrf_token")
        return {"X-CSRF-Token": token} if token else {}

    def get(self, path: str, **kwargs: Any) -> Response:
        return self.http.get(path, **kwargs)

    def send(self, method: str, path: str, **kwargs: Any) -> Response:
        headers = self._csrf() | kwargs.pop("headers", {})
        return self.http.request(method, path, headers=headers, **kwargs)

    def sign_in(self, email: str) -> str:
        """Log in, or sign up the first time. Returns the handle."""
        body = {"email": email, "password": PASSWORD}
        response = self.send("POST", "/api/auth/login", json=body)
        if response.status_code == 401:
            response = self.send("POST", "/api/auth/signup", json=body)
        assert response.status_code in (200, 201), response.text
        return response.json()["handle"]


@pytest.fixture
def owner() -> Iterator[Browser]:
    browser = Browser()
    browser.sign_in("e2e-owner@example.com")
    yield browser
    browser.http.close()


@pytest.fixture
def stranger() -> Iterator[tuple[Browser, str]]:
    browser = Browser()
    handle = browser.sign_in("e2e-stranger@example.com")
    yield browser, handle
    browser.http.close()


@pytest.fixture
def guest() -> Iterator[Browser]:
    browser = Browser()
    yield browser
    browser.http.close()


def ffmpeg(*args: str) -> None:
    subprocess.run(  # noqa: S603 fixed commands, no user input
        ["ffmpeg", "-nostdin", "-v", "error", "-y", *args],  # noqa: S607 ffmpeg from PATH
        check=True,
    )


def video_height(path: Path) -> int:
    entries = ["-select_streams", "v:0", "-show_entries", "stream=height", "-of", "json"]
    command = ["ffprobe", "-v", "error", *entries, str(path)]
    out = subprocess.run(command, check=True, capture_output=True).stdout  # noqa: S603
    return json.loads(out)["streams"][0]["height"]


def upload(browser: Browser, content: bytes, title: str) -> str:
    draft = browser.send("POST", "/api/videos", json={"title": title})
    assert draft.status_code == 201, draft.text
    public_id = draft.json()["id"]
    stored = browser.send("PUT", f"/api/videos/{public_id}/file", content=content)
    assert stored.status_code == 200, stored.text
    assert stored.json()["status"] == "uploaded"
    return public_id


def listed(browser: Browser, path: str, **params: str) -> list[str]:
    """Ids on the first page of a public list: the feed or search."""
    response = browser.get(path, params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def wait_until_processed(browser: Browser, public_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + PROCESSING_TIMEOUT_SEC
    while time.monotonic() < deadline:
        video = browser.get(f"/api/videos/{public_id}").json()
        if video["status"] in ("ready", "failed"):
            return video
        time.sleep(1)
    pytest.fail(f"Video {public_id} not processed in {PROCESSING_TIMEOUT_SEC} s")


def test_upload_processing_playback_and_access(
    owner: Browser, stranger: tuple[Browser, str], guest: Browser, tmp_path: Path
) -> None:
    other, other_handle = stranger
    sample = tmp_path / "sample.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=3:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=duration=3",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(sample),
    )  # fmt: skip

    # Upload → processing → ready. The marker finds this run's video among earlier runs'.
    marker = secrets.token_hex(4)
    public_id = upload(owner, sample.read_bytes(), f"E2E private video {marker}")
    video = wait_until_processed(owner, public_id)
    assert video["status"] == "ready", video["error_message"]
    assert video["duration_sec"] == 3
    page, media, thumbnail = f"/api/videos/{public_id}", video["media_url"], video["thumbnail_url"]

    # Playback: Range requests (seeking) and a 720p MP4.
    part = owner.get(media, headers={"Range": "bytes=0-1023"})
    assert part.status_code == 206
    assert part.headers["content-type"] == "video/mp4"
    assert part.headers["content-range"].startswith("bytes 0-1023/")
    assert len(part.content) == 1024
    whole = tmp_path / "out.mp4"
    whole.write_bytes(owner.get(media).content)
    assert video_height(whole) == 720
    image = owner.get(thumbnail)
    assert (image.status_code, image.headers["content-type"]) == (200, "image/jpeg")

    # Same origin only; MinIO's error bodies (bucket and key names) don't reach the browser.
    cross = owner.get(media, headers={"Origin": "https://evil.example", "Range": "bytes=0-99"})
    assert "access-control-allow-origin" not in cross.headers
    assert cross.headers["cross-origin-resource-policy"] == "same-origin"
    beyond = owner.get(media, headers={"Range": "bytes=999999999-"})
    assert beyond.status_code == 416
    assert b"<Error>" not in beyond.content

    # Private: a guest must sign in, a stranger learns nothing; originals are never served.
    assert public_id not in listed(guest, "/api/videos")
    assert public_id not in listed(guest, "/api/search", q=marker)
    assert guest.get(page).status_code == 404
    assert guest.get(media).status_code == 401
    assert other.get(page).status_code == 404
    assert other.get(media).status_code == 404
    video_uuid = media.split("/")[3]
    assert owner.get(f"/media/originals/{video_uuid}").status_code == 404

    # Shared: the stranger can watch; taken back: at once, the page and the file.
    shared = owner.send("POST", f"{page}/access", json={"handle": other_handle})
    assert shared.status_code == 204
    assert other.get(page).status_code == 200
    assert other.get(media, headers={"Range": "bytes=0-99"}).status_code == 206
    assert owner.send("DELETE", f"{page}/access/{other_handle}").status_code == 204
    assert other.get(page).status_code == 404
    assert other.get(media, headers={"Range": "bytes=0-99"}).status_code == 404

    # Public: anyone, no cookie needed; on the home feed and found by its title.
    assert owner.send("PATCH", page, json={"visibility": "public"}).status_code == 200
    assert guest.get(page).status_code == 200
    assert guest.get(media, headers={"Range": "bytes=0-99"}).status_code == 206
    assert public_id in listed(guest, "/api/videos")
    assert public_id in listed(guest, "/api/search", q=marker)

    # Private again: out of the lists at once. Runs leave no public test videos behind.
    assert owner.send("PATCH", page, json={"visibility": "private"}).status_code == 200
    assert public_id not in listed(guest, "/api/videos")
    assert public_id not in listed(guest, "/api/search", q=marker)


def test_a_file_that_is_not_a_video_fails_with_a_reason(owner: Browser) -> None:
    public_id = upload(owner, b"just some text, not a video", "E2E not a video")

    video = wait_until_processed(owner, public_id)

    assert video["status"] == "failed"
    assert video["error_message"] == "The file is not a video or is damaged"


def test_internal_routes_are_closed_from_outside(guest: Browser) -> None:
    assert guest.get("/internal/media-auth").status_code == 404
