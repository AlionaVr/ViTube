"""Liked videos on a running stack, through nginx: a like lists a video, lost access removes it.

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
Accounts are reused between runs: the viewer's other likes may be there, so checks look at the top
of the list and at the count's change. A run ends with the like taken back and its video private.
"""

import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.test_scenario import BASE_URL, Browser, ffmpeg, upload, wait_until_processed

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")

LIKED = "/api/me/liked"


def signed_in(email: str) -> Iterator[Browser]:
    browser = Browser()
    browser.sign_in(email)
    yield browser
    browser.http.close()


@pytest.fixture
def owner() -> Iterator[Browser]:
    yield from signed_in("e2e-owner@example.com")  # the scenario's accounts


@pytest.fixture
def viewer() -> Iterator[Browser]:
    yield from signed_in("e2e-stranger@example.com")


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def rate(browser: Browser, public_id: str, rating: str) -> None:
    ok(browser.send("PUT", f"/api/videos/{public_id}/rating", json={"rating": rating}))


def first_page(browser: Browser) -> list[str]:
    return [item["video"]["id"] for item in ok(browser.get(f"{LIKED}/items"))["items"]]


def count(browser: Browser) -> int:
    return ok(browser.get(LIKED))["video_count"]


def set_visibility(owner: Browser, public_id: str, visibility: str) -> None:
    ok(owner.send("PATCH", f"/api/videos/{public_id}", json={"visibility": visibility}))


def test_liked_videos(owner: Browser, viewer: Browser, tmp_path: Path) -> None:
    sample = tmp_path / "sample.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=duration=3",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(sample),
    )  # fmt: skip
    video = upload(owner, sample.read_bytes(), f"E2E liked {secrets.token_hex(4)}")
    assert wait_until_processed(owner, video)["status"] == "ready"
    set_visibility(owner, video, "public")
    before = count(viewer)

    # A like puts the video on top; the header counts it and takes its cover.
    rate(viewer, video, "like")
    assert first_page(viewer)[0] == video
    header = ok(viewer.get(LIKED))
    assert header["video_count"] == before + 1
    assert header["thumbnail_url"] == ok(viewer.get(f"/api/videos/{video}"))["thumbnail_url"]

    # Private without a grant: gone from the list and the count; back when it is public again.
    set_visibility(owner, video, "private")
    assert video not in first_page(viewer)
    assert count(viewer) == before
    set_visibility(owner, video, "public")
    assert first_page(viewer)[0] == video

    # Taking the like back removes it.
    rate(viewer, video, "none")
    assert video not in first_page(viewer)
    assert count(viewer) == before
    set_visibility(owner, video, "private")


def test_a_guest_has_no_liked_videos() -> None:
    guest = Browser()
    try:
        assert guest.get(LIKED).status_code == 401
        assert guest.get(f"{LIKED}/items").status_code == 401
    finally:
        guest.http.close()
