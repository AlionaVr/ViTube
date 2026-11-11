"""Patterns for text from users. Postgres refuses NUL (a 500, not a 422); other control
characters only garble the page."""

# One line: no control characters at all.
SINGLE_LINE = r"^[^\x00-\x1f\x7f]*$"
# Tab and newlines allowed.
MULTILINE = r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"
