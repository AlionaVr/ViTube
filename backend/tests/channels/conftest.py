"""Signed-in clients for channel tests: the same fixtures as the interaction tests."""

from tests.interactions.conftest import guest, make_viewers, owner, viewer

__all__ = ["guest", "make_viewers", "owner", "viewer"]
