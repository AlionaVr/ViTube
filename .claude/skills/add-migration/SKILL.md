---
name: add-migration
description: Create and review an Alembic migration for ViTube after changing SQLAlchemy models.
---

# Add a migration

1. Change models in `backend/app/modules/<domain>/models.py`. Make sure the module is imported in `app/db/models.py` so
   Alembic sees it.
2. Generate. The code is baked into the image (built by the `api` service), so rebuild it and mount only `versions/` to get the file back:
   `docker compose build api && docker compose run --rm --user "$(id -u):$(id -g)" -v ./backend/alembic/versions:/app/alembic/versions migrate alembic revision --autogenerate -m "<short message>"`.
   Then in `backend/`: `uv run ruff format alembic && uv run ruff check --fix alembic`.
3. Review the file in `backend/alembic/versions/`. Autogenerate often misses:
    - PostgreSQL enums (create/drop types);
    - generated columns (`tsvector`) and GIN / trigram indexes;
    - extensions (the baseline has `citext` and `pg_trgm`; add others by hand);
    - server defaults and CHECK constraints.
4. Make sure `downgrade()` really reverses `upgrade()`.
5. Apply: `docker compose build api && docker compose run --rm migrate`. Test: `docker compose run --rm migrate alembic downgrade -1`, then
   `... alembic upgrade head`.
6. Never edit a migration that was already committed. Add a new one.
7. For bigger schema changes, ask the `db-reviewer` agent.
