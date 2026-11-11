"""Channels, subscriptions and playlists on a running stack, through nginx.

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
Accounts are reused between runs, so counts are checked as changes, and each run cleans up after
itself: its videos end private, its playlist deleted, the subscription gone.
"""

import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.test_scenario import BASE_URL, Browser, ffmpeg, upload, wait_until_processed

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")


def signed_in(email: str) -> Iterator[tuple[Browser, str]]:
    browser = Browser()
    handle = browser.sign_in(email)
    yield browser, handle
    browser.http.close()


@pytest.fixture
def owner() -> Iterator[tuple[Browser, str]]:
    yield from signed_in("e2e-owner@example.com")  # the scenario's accounts


@pytest.fixture
def fan() -> Iterator[tuple[Browser, str]]:
    yield from signed_in("e2e-stranger@example.com")


@pytest.fixture
def guest() -> Iterator[Browser]:
    browser = Browser()
    yield browser
    browser.http.close()


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def ids(browser: Browser, path: str) -> list[str]:
    """Ids on the first page of a list."""
    return [item.get("id") or item["video"]["id"] for item in ok(browser.get(path))["items"]]


def test_channel_subscriptions_and_playlists(
    owner: tuple[Browser, str],
    fan: tuple[Browser, str],
    guest: Browser,
    tmp_path: Path,
) -> None:
    anna, anna_handle = owner
    bob, bob_handle = fan
    channel = f"/api/channels/{anna_handle}"
    sample = tmp_path / "sample.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=duration=2",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(sample),
    )  # fmt: skip

    # Two public videos on Anna's channel.
    marker = secrets.token_hex(4)
    first, second = (upload(anna, sample.read_bytes(), f"E2E channel {n} {marker}") for n in (1, 2))
    for public_id in (first, second):
        assert wait_until_processed(anna, public_id)["status"] == "ready"
        ok(anna.send("PATCH", f"/api/videos/{public_id}", json={"visibility": "public"}))
    assert {first, second} <= set(ids(guest, f"{channel}/videos"))

    # Subscribe: twice is once. The channel, the list and the feed agree.
    bob.send("DELETE", f"{channel}/subscription")  # a failed earlier run may have left it
    before = ok(guest.get(channel))["subscriber_count"]
    for _ in range(2):
        answer = ok(bob.send("PUT", f"{channel}/subscription"))
        assert answer == {"subscriber_count": before + 1, "is_subscribed": True}
    assert ok(bob.get(channel))["is_subscribed"] is True
    assert ok(guest.get(channel))["is_subscribed"] is False
    assert anna_handle in [c["handle"] for c in ok(bob.get("/api/me/subscriptions"))["items"]]
    assert {first, second} <= set(ids(bob, "/api/feed/subscriptions"))
    assert ok(anna.send("PUT", f"/api/channels/{anna_handle}/subscription"), 400)  # not yourself

    # Bob's public playlist with both videos, reordered; guests see it on his channel.
    playlist_id = ok(
        bob.send("POST", "/api/playlists", json={"title": f"E2E {marker}", "visibility": "public"}),
        201,
    )["id"]
    playlist = f"/api/playlists/{playlist_id}"
    for public_id in (first, second, first):  # adding again changes nothing
        ok(bob.send("PUT", f"{playlist}/items/{public_id}"), 204)
    ok(bob.send("PATCH", f"{playlist}/items/{second}", json={"before": first}), 204)
    assert ids(guest, f"{playlist}/items") == [second, first]
    assert ok(guest.get(playlist))["video_count"] == 2
    assert playlist_id in ids(guest, f"/api/channels/{bob_handle}/playlists")
    assert ok(anna.send("PUT", f"{playlist}/items/{first}"), 404)  # not hers
    assert ok(bob.get(f"/api/videos/{first}/saved"))["saved"] is True

    # Private again: out of the channel, the feed and others' view of the playlist, at once.
    ok(anna.send("PATCH", f"/api/videos/{first}", json={"visibility": "private"}))
    assert first not in ids(guest, f"{channel}/videos")
    assert first not in ids(bob, "/api/feed/subscriptions")
    assert ids(guest, f"{playlist}/items") == [second]
    assert ok(guest.get(playlist))["video_count"] == 2  # still in it, just not watchable

    # Watch later is Bob's own and stays private and in place.
    watch_later = ok(bob.get("/api/me/watch-later"))
    assert (watch_later["kind"], watch_later["visibility"]) == ("watch_later", "private")
    assert ok(guest.get(f"/api/playlists/{watch_later['id']}"), 404)
    assert ok(bob.send("DELETE", f"/api/playlists/{watch_later['id']}"), 400)

    # The pages exist in the web app.
    for path in (f"/@{anna_handle}/playlists", "/feed/playlists", f"/playlist?list={playlist_id}"):
        page = guest.get(path)
        assert (page.status_code, page.headers["content-type"].split(";")[0]) == (200, "text/html")

    # Clean up: deleted, unsubscribed (twice is once), no public test videos left.
    ok(bob.send("DELETE", playlist), 204)
    assert ok(guest.get(playlist), 404)
    assert playlist_id not in ids(guest, f"/api/channels/{bob_handle}/playlists")
    for _ in range(2):
        answer = ok(bob.send("DELETE", f"{channel}/subscription"))
        assert answer == {"subscriber_count": before, "is_subscribed": False}
    ok(anna.send("PATCH", f"/api/videos/{second}", json={"visibility": "private"}))
    assert second not in ids(guest, f"{channel}/videos")
