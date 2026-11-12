"""Postgres advisory lock ids."""

# Any fixed number shared by every migration run: a second run waits for the first one.
MIGRATIONS = 2026_11_04

# With a user id's hash: their writes (shared) against changes of their status or role
# (exclusive), ADR 0005. Two-key form, so it never meets MIGRATIONS.
USER_WRITES = 2026_11_12
