# ViTube — Plan and Requirements

A YouTube clone built with AI. Stack: FastAPI, PostgreSQL, React. Key decisions and their reasons are
in [adr/](adr/README.md).

## Goals (how it's graded)

Scope · likeness to YouTube · one-command deploy on clean Ubuntu · architecture · DB design · AI tooling · security ·
git history.

Must work right after deploy: **register → upload → watch → like → comment**.

## Roles

| Role      | Can                                                                             |
|-----------|---------------------------------------------------------------------------------|
| guest     | watch public/unlisted, search, read comments                                    |
| user      | + upload, like, comment, subscribe, playlists, report, share own private videos |
| moderator | + review reports, hide/restore videos, delete comments                          |
| admin     | + set roles (CLI), ban users, terminate channels, read audit log                |

## Screens

YouTube layout: header with logo, search and avatar; collapsible sidebar.

1. **Home** — video grid (thumbnail + duration, channel avatar, title, views, age), category chips, infinite scroll.
2. **Watch** `/watch?v=<id>`:
    - player with seeking;
    - title, channel + Subscribe, like/dislike, Share, Save, Report;
    - description, comments with replies;
    - "Up next" list.
3. **Channel** `/@handle` — banner, avatar, subscribers. Tabs: Videos, Playlists, About. Owner can edit videos and share
   private ones.
4. **Search** `/results?search_query=` — YouTube-style list, suggestions while typing.
5. **Upload** — drag & drop, progress bar, metadata form, processing status, clear limit errors.
6. **Sign in / Sign up** — email and password, or Google when it is set up
   ([ADR 0014](adr/0014-google-sign-in.md)); the server gives a random @handle (editable later). A channel is
   created on sign-up.
7. **Moderation** `/moderation` — report queue, hidden videos; for admins, restricted accounts and the audit log
   with filters.
8. **History** `/feed/history` — watched videos by day: search, remove, clear, pause. A red bar on every thumbnail
   shows where the viewer stopped; the video resumes there.
9. **Liked videos** `/playlist?list=LL` — the viewer's likes as a private playlist, newest like first; ⋮ takes a
   like back. A card on the Playlists page `/feed/playlists`, before Watch later.

## Acceptance

- **Core flow:** register → upload → video becomes `READY` → appears in feed and search → plays with seeking → like →
  comment.
- **Private video, stranger:** gets 404 on the page and on `/media/...`.
- **Private video, after access is granted:** the user can watch.
- **Media without a cookie:** 401.
- **Hidden video or terminated channel:** 404 for everyone but the owner (hidden only) and moderators, on the page
  and on `/media/...`; never in lists.
- **Banned user:** open sessions stop working at once; signing in is refused.

## Architecture

```
Browser ──:80──► nginx ─┬─ /             → React static files
                        ├─ /api/*, /docs → api (FastAPI)
                        └─ /media/*      → auth_request → minio
api    ──► postgres, redis, minio
worker (Celery + ffmpeg) ◄── redis; ──► minio, postgres
one-shot jobs: migrate, minio-init, seed
```

Backend layers per domain module: `router → service → repository → models`, with Pydantic `schemas` for input and
output.
One access policy, `can_view(user, video)`, is used everywhere.

## Database

| Table             | Key fields / constraints                                                                                                                             |
|-------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| `users`           | email, handle (citext, unique), password_hash, role, status (active / banned / terminated), avatar, banner, history_paused                           |
| `videos`          | public_id (11 chars), owner, title, description, visibility, status, is_hidden, duration, counters, `search_vector` (GIN), title trigram (GIN)       |
| `video_access`    | (video, user); only the owner grants                                                                                                                 |
| `video_reactions` | (user, video), value ±1, rated_at; Liked videos read from it ([ADR 0013](adr/0013-liked-videos.md))                                                  |
| `comments`        | video, author, parent (replies), is_deleted                                                                                                          |
| `subscriptions`   | (subscriber, channel), check: not self                                                                                                               |
| `playlists`       | owner, title, visibility, kind = user / watch_later                                                                                                  |
| `playlist_items`  | (playlist, video), position                                                                                                                          |
| `watch_history`   | (user, video), position_sec, watched_at ([ADR 0012](adr/0012-watch-history.md))                                                                      |
| `reports`         | reporter, target (video xor comment), reason, status, resolved_by                                                                                    |
| `audit_log`       | source (api / cli), actor, action, target, details jsonb; append-only, no foreign keys                                                               |

Not in Postgres: sessions, rate limits and view de-duplication live in Redis.
Object keys are built from `videos.id` ([ADR 0002](adr/0002-object-storage-minio.md)), so they aren't stored.

## Roadmap

Each stage is a vertical slice: backend + frontend + tests, built as a walking skeleton first. It is done when its
flow works on the stack, and it ends with a PR.

| Day | Stage                                                                                                                           |
|-----|---------------------------------------------------------------------------------------------------------------------------------|
| 1   | 0 Bootstrap (docs, AI tooling) · 1 Infra (compose, skeletons, `install.sh`)                                                     |
| 1–2 | 2 Auth · 3 Upload + worker                                                                                                      |
| 2–3 | 4 Media access · 5 Watch page                                                                                                   |
| 3–4 | 6 Home, search, channel, subscriptions, playlists · 7 Moderation                                                                |
| 4   | 8 Seed, docs, clean VM check                                                                                                    |
| 5–6 | 9 Extras: history, watch later, subscriptions feed · comment sorting, dark theme, custom player controls · HLS · chunked upload |
| 7   | 10 Polish: UI review, security review, clean VM re-check                                                                        |

## Verification

- **Checks:** `pytest`, `ruff`, `pyright`, frontend build and tests.
- **Clean Ubuntu VM:** `./install.sh` → site at `http://<ip>/`, Swagger at `/docs`, demo data present.
- **E2E:** `tests/e2e/test_scenario.py` runs the core flow and the private-video checks; `test_moderation.py` runs
  report, hide, restore, comment delete, ban, terminate and the audit log.
