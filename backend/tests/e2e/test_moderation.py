"""Moderation on a running stack: report → queue → hide and restore, comment delete, ban, terminate,
and the audit log that names who did each (ADR 0009).

Run: E2E_BASE_URL=http://localhost uv run pytest tests/e2e -v   (needs ffmpeg for the sample video)
Roles have no API: the test gives them with the CLI, so the stack must run from this checkout.
"""

import secrets
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.test_scenario import (
    BASE_URL,
    PASSWORD,
    Browser,
    ffmpeg,
    listed,
    upload,
    wait_until_processed,
)

pytestmark = pytest.mark.skipif(not BASE_URL, reason="needs a running stack: set E2E_BASE_URL")

REPO = Path(__file__).resolve().parents[3]
OWNER, REPORTER = "e2e-owner@example.com", "e2e-stranger@example.com"  # the scenario's accounts
ADMIN = "e2e-admin@example.com"


def cli(*args: str) -> str:
    """The admin CLI in the stack's api container."""
    command = ["docker", "compose", "exec", "-T", "api", "python", "-m", "app.cli", *args]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def signed_in(email: str, role: str | None = None) -> Iterator[Browser]:
    # Sign-ups are limited per IP: runs reuse these accounts.
    browser = Browser()
    browser.sign_in(email)
    if role:
        cli("set-role", email, role)  # applies to the open session at once
    yield browser
    browser.http.close()


@pytest.fixture
def owner() -> Iterator[Browser]:
    yield from signed_in(OWNER)


@pytest.fixture
def reporter() -> Iterator[Browser]:
    yield from signed_in(REPORTER)


@pytest.fixture
def moderator() -> Iterator[Browser]:
    yield from signed_in("e2e-moderator@example.com", "moderator")


@pytest.fixture
def admin() -> Iterator[Browser]:
    yield from signed_in(ADMIN, "admin")


@pytest.fixture
def guest() -> Iterator[Browser]:
    browser = Browser()
    yield browser
    browser.http.close()


def ok(response: Any, status: int = 204) -> Any:
    assert response.status_code == status, response.text
    return response


def find_case(moderator: Browser, public_id: str) -> dict[str, Any]:
    """The video's case in the queue, oldest first: earlier runs' cases may come before it."""
    cursor = None
    while True:
        params = {"cursor": cursor} if cursor else {}
        page = ok(moderator.get("/api/moderation/reports", params=params), 200).json()
        for case in page["items"]:
            if case["video"] and case["video"]["id"] == public_id:
                return case
        if not (cursor := page["next_cursor"]):
            pytest.fail(f"No case for {public_id}")


def audit(admin: Browser, **params: str) -> list[dict[str, Any]]:
    return ok(admin.get("/api/moderation/audit-log", params=params), 200).json()["items"]


def test_report_hide_restore_ban_terminate_and_audit(
    owner: Browser,
    reporter: Browser,
    moderator: Browser,
    admin: Browser,
    guest: Browser,
    tmp_path: Path,
) -> None:
    owner_handle = ok(owner.get("/api/auth/me"), 200).json()["handle"]
    reporter_handle = ok(reporter.get("/api/auth/me"), 200).json()["handle"]
    moderator_handle = ok(moderator.get("/api/auth/me"), 200).json()["handle"]
    sample = tmp_path / "sample.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=30",
        "-c:v", "libx264", str(sample),
    )  # fmt: skip
    marker = secrets.token_hex(4)
    public_id = upload(owner, sample.read_bytes(), f"E2E reported video {marker}")
    video = wait_until_processed(owner, public_id)
    assert video["status"] == "ready", video["error_message"]
    page, media = f"/api/videos/{public_id}", video["media_url"]
    ok(owner.send("PATCH", page, json={"visibility": "public"}), 200)

    # A viewer reports it; the queue shows the case. Users don't see the queue.
    report = {"reason": "spam", "details": f"E2E {marker}"}
    ok(guest.send("POST", f"{page}/report", json=report), 401)
    ok(reporter.send("POST", f"{page}/report", json=report))
    ok(reporter.get("/api/moderation/reports"), 403)
    case = find_case(moderator, public_id)
    assert (case["report_count"], case["reasons"]) == (1, ["spam"])

    # Hidden: gone for others, page and file; the owner still opens it, frozen.
    ok(moderator.send("POST", f"/api/moderation/videos/{public_id}/hide", json={"reason": "spam"}))
    ok(guest.get(page), 404)
    ok(guest.get(media), 401)
    ok(reporter.get(page), 404)
    assert public_id not in listed(guest, "/api/search", q=marker)
    assert ok(owner.get(page), 200).json()["is_hidden"] is True
    ok(owner.get(media, headers={"Range": "bytes=0-99"}), 206)
    ok(owner.send("POST", f"{page}/comments", json={"text": "Why?"}), 404)

    # Restored: back for everyone.
    ok(moderator.send("POST", f"/api/moderation/videos/{public_id}/restore"))
    ok(guest.get(page), 200)
    assert public_id in listed(guest, "/api/search", q=marker)

    # A reported comment, deleted by the moderator.
    comment = ok(reporter.send("POST", f"{page}/comments", json={"text": "Cheap followers"}), 201)
    comment_id = comment.json()["id"]
    ok(owner.send("POST", f"/api/comments/{comment_id}/report", json={"reason": "spam"}))
    ok(moderator.send("DELETE", f"/api/moderation/comments/{comment_id}"))
    comments = ok(guest.get(f"{page}/comments"), 200).json()["items"]
    assert comment_id not in [item["id"] for item in comments]

    try:
        # Banned: the open session is useless at once, and signing in is refused.
        ban = {"status": "banned", "reason": f"E2E {marker}"}
        ok(moderator.send("PUT", f"/api/moderation/users/{reporter_handle}/status", json=ban), 403)
        ok(admin.send("PUT", f"/api/moderation/users/{reporter_handle}/status", json=ban))
        ok(reporter.get("/api/auth/me"), 401)
        login = {"email": REPORTER, "password": PASSWORD}
        ok(Browser().send("POST", "/api/auth/login", json=login), 403)

        # Terminated: the channel's videos are gone for all but staff, with no change to them.
        terminate = {"status": "terminated"}
        ok(admin.send("PUT", f"/api/moderation/users/{owner_handle}/status", json=terminate))
        ok(guest.get(page), 404)
        assert ok(moderator.get(page), 200).json()["channel_terminated"] is True
    finally:
        # Reinstated, also when a step above failed: later runs need these accounts.
        done = ("--by", ADMIN, "--reason", "E2E done")
        cli("set-status", REPORTER, "active", *done)
        cli("set-status", OWNER, "active", *done)
    ok(guest.get(page), 200)

    # The audit log names who did what; filters find the account and the moderator's acts.
    about_owner = audit(admin, account=owner_handle)
    acts = [(entry["action"], entry["source"]) for entry in about_owner[:4]]
    assert acts == [
        ("set_user_status", "cli"),
        ("set_user_status", "api"),
        ("restore_video", "api"),
        ("hide_video", "api"),
    ]
    assert about_owner[3]["actor"]["handle"] == moderator_handle
    assert about_owner[3]["target"]["video_id"] == public_id
    deleted = audit(admin, actor=moderator_handle, action="delete_comment")
    assert deleted[0]["target"]["type"] == "comment"
    ok(moderator.get("/api/moderation/audit-log"), 403)

    # Private again: runs leave no public test videos behind. The owner's sessions ended.
    owner.sign_in(OWNER)
    ok(owner.send("PATCH", page, json={"visibility": "private"}), 200)
