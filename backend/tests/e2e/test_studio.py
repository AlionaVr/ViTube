"""Studio on a running stack: the owner's list shows every video with its real status.

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.test_scenario import BASE_URL, Browser, ffmpeg, upload, wait_until_processed

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")


def signed_in(email: str) -> Iterator[Browser]:
    # The scenario's accounts: sign-ups are limited per IP, so runs make no new ones.
    browser = Browser()
    browser.sign_in(email)
    yield browser
    browser.http.close()


@pytest.fixture
def owner() -> Iterator[Browser]:
    yield from signed_in("e2e-owner@example.com")


@pytest.fixture
def stranger() -> Iterator[Browser]:
    yield from signed_in("e2e-stranger@example.com")


def my_videos(browser: Browser) -> list[dict[str, Any]]:
    response = browser.get("/api/me/videos")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_studio_lists_drafts_failed_and_private_videos(owner: Browser, tmp_path: Path) -> None:
    sample = tmp_path / "sample.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25", str(sample))
    draft = owner.send("POST", "/api/videos", json={"title": "E2E studio draft"})
    assert draft.status_code == 201, draft.text
    broken = upload(owner, b"just some text, not a video", "E2E studio broken")
    private = upload(owner, sample.read_bytes(), "E2E studio private")
    wait_until_processed(owner, broken)
    wait_until_processed(owner, private)

    # Newest first: this run's three on top of earlier runs' videos.
    newest = my_videos(owner)[:3]

    assert [(item["id"], item["status"], item["visibility"]) for item in newest] == [
        (private, "ready", "private"),
        (broken, "failed", "private"),
        (draft.json()["id"], "uploading", "private"),
    ]
    assert newest[1]["error_message"] == "The file is not a video or is damaged"
    # Studio shows the private thumbnail: /media lets its owner fetch it.
    image = owner.get(newest[0]["thumbnail_url"])
    assert (image.status_code, image.headers["content-type"]) == (200, "image/jpeg")


def test_others_never_see_them_and_a_guest_must_sign_in(owner: Browser, stranger: Browser) -> None:
    public_id = upload(owner, b"just some text, not a video", "E2E studio not for others")

    assert public_id not in [item["id"] for item in my_videos(stranger)]
    assert Browser().get("/api/me/videos").status_code == 401
