"""Keyset pages: a list returns `next_cursor`, the client sends it back for the next page.

The cursor holds the sort key of the last item, so the next query starts right after it
(`WHERE (a, b) < (:a, :b)`). Unlike OFFSET, new rows on top don't shift pages.

Pages are exact only if a row's sort key never changes. With a changing key (e.g. like count)
a row can move past the cursor: it is skipped, or shows twice. Clients drop repeats by id.
"""

import base64
import binascii
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import to_json

from app.core.errors import DomainError


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


class InvalidCursor(DomainError):
    detail = "Invalid cursor"


def encode_cursor(key: tuple[Any, ...]) -> str:
    return base64.urlsafe_b64encode(to_json(key)).decode()


def decode_cursor[K](cursor: str, shape: type[K]) -> K:
    """The sort key from a cursor, checked against its shape, e.g. tuple[int, UUID]."""
    try:
        return TypeAdapter(shape).validate_json(base64.urlsafe_b64decode(cursor))
    except (binascii.Error, ValueError, ValidationError):
        raise InvalidCursor() from None


def split_page[R](
    rows: Sequence[R], size: int, key: Callable[[R], tuple[Any, ...]]
) -> tuple[Sequence[R], str | None]:
    """Rows fetched with LIMIT size + 1: the extra row only shows that a next page exists."""
    if len(rows) <= size:
        return rows, None
    return rows[:size], encode_cursor(key(rows[size - 1]))
