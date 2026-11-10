"""Keyset page cursors."""

from uuid import UUID

import pytest

from app.core.pagination import InvalidCursor, decode_cursor, encode_cursor, split_page

ID = UUID("01900000-0000-7000-8000-000000000001")


def test_cursor_round_trip() -> None:
    cursor = encode_cursor((42, ID))

    assert decode_cursor(cursor, tuple[int, UUID]) == (42, ID)


@pytest.mark.parametrize(
    "cursor",
    [
        "not base64!",
        encode_cursor(("many", ID)),  # wrong type
        encode_cursor((42,)),  # wrong length
        encode_cursor((42, "not-a-uuid")),
        "",
    ],
)
def test_bad_cursor_is_refused(cursor: str) -> None:
    with pytest.raises(InvalidCursor) as error:
        decode_cursor(cursor, tuple[int, UUID])

    assert error.value.status_code == 400


def test_full_page_without_more_rows_has_no_cursor() -> None:
    rows, cursor = split_page([1, 2, 3], 3, lambda row: (row,))

    assert list(rows) == [1, 2, 3]
    assert cursor is None


def test_extra_row_gives_a_cursor_after_the_last_kept_row() -> None:
    rows, cursor = split_page([1, 2, 3, 4], 3, lambda row: (row,))

    assert list(rows) == [1, 2, 3]
    assert cursor is not None
    assert decode_cursor(cursor, tuple[int]) == (3,)
