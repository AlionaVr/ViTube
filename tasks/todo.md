# Todo

Current stage plan. Full roadmap: `docs/plan.md`.

## Stage 0 — Bootstrap

- [x] Plan and ADRs
- [x] Claude Code config: CLAUDE.md, hooks, agents, skills
- [x] .gitignore

## Stage 1 — Infra

Decisions: MinIO image `pgsty/minio` (official images are gone), Python 3.13.

- [x] Backend skeleton: uv project, settings from env, `/api/health`, Swagger at `/docs`, test
- [x] Alembic: naming convention, async `env.py`, baseline migration (`citext`, `pg_trgm`)
- [x] Celery app for the worker (no tasks yet)
- [x] Frontend skeleton: Vite + React Router, header + collapsible sidebar, CSS tokens, test
- [x] Docker: backend and frontend Dockerfiles, nginx config, `compose.yaml`, `.env.example`
- [x] Verify: stack healthy, migrations up/down, bucket created, re-run is idempotent, UI screenshot
- [x] ADR 0002 note on the MinIO image; `CLAUDE.md` commands
- [ ] `install.sh`

## Deferred UI notes (from youtube-ui-reviewer)

- Stage 6 search: focus state (box grows left, icon inside), own clear button instead of Chrome's.
- Dark theme stage: ⋮ Settings button left of Sign in (holds Appearance).
- Polish: overlay drawer on narrow screens; collapsed search at ≤656px.
