"""Watch history on a running stack, through nginx: saves, progress, search, pause, removal.

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
Accounts are reused between runs, so each run starts by clearing the viewer's history and ends
with it cleared, turned on, and its video private.
"""

import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.test_scenario import BASE_URL, Browser, ffmpeg, upload, wait_until_processed

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")

HISTORY = "/api/me/history"


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
    return response.json() if response.content else None


def listed(browser: Browser, words: str | None = None) -> list[str]:
    params = {"q": words} if words else {}
    return [item["video"]["id"] for item in ok(browser.get(HISTORY, params=params))["items"]]


def save(browser: Browser, public_id: str, seconds: int) -> None:
    ok(browser.send("PUT", f"{HISTORY}/{public_id}", json={"position_sec": seconds}), 204)


def test_watch_history(owner: Browser, viewer: Browser, tmp_path: Path) -> None:
    sample = tmp_path / "sample.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=duration=3",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(sample),
    )  # fmt: skip
    marker = secrets.token_hex(4)
    video = upload(owner, sample.read_bytes(), f"E2E history {marker}")
    processed = wait_until_processed(owner, video)
    assert processed["status"] == "ready"
    length = processed["duration_sec"]
    ok(owner.send("PATCH", f"/api/videos/{video}", json={"visibility": "public"}))
    # A failed earlier run may have left it paused or full.
    ok(viewer.send("PUT", f"{HISTORY}/settings", json={"paused": False}))
    ok(viewer.send("DELETE", HISTORY), 204)

    # The player saves; past the end counts as the end. The bar and the list show it.
    save(viewer, video, 1)
    save(viewer, video, 600)
    assert ok(viewer.get(f"{HISTORY}/progress", params={"v": video})) == {video: length}
    assert listed(viewer) == [video]
    assert listed(viewer, marker) == [video]
    assert listed(viewer, f"{marker} -history") == []

    # Paused: nothing new is saved, what is there stays.
    ok(viewer.send("PUT", f"{HISTORY}/settings", json={"paused": True}))
    save(viewer, video, 0)
    assert ok(viewer.get(f"{HISTORY}/progress", params={"v": video})) == {video: length}
    ok(viewer.send("PUT", f"{HISTORY}/settings", json={"paused": False}))

    # Private: out of the viewer's list, kept for the owner's own history.
    save(owner, video, 2)
    ok(owner.send("PATCH", f"/api/videos/{video}", json={"visibility": "private"}))
    assert video not in listed(viewer)
    assert listed(owner)[0] == video
    ok(owner.send("PATCH", f"/api/videos/{video}", json={"visibility": "public"}))
    assert listed(viewer) == [video]

    # Removed: the row and its bar go; the page exists in the web app.
    ok(viewer.send("DELETE", f"{HISTORY}/{video}"), 204)
    assert listed(viewer) == []
    assert ok(viewer.get(f"{HISTORY}/progress", params={"v": video})) == {}
    page = viewer.get("/feed/history")
    assert (page.status_code, page.headers["content-type"].split(";")[0]) == (200, "text/html")

    # Clean up: no public test video, the owner's entry gone.
    ok(owner.send("DELETE", f"{HISTORY}/{video}"), 204)
    ok(owner.send("PATCH", f"/api/videos/{video}", json={"visibility": "private"}))
