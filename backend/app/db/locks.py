"""Postgres advisory lock ids."""

# Any fixed number shared by every migration run: a second run waits for the first one.
MIGRATIONS = 2026_11_04
