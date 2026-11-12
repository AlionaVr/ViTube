# ViTube

[![CI](https://github.com/AlionaVr/Vitube/actions/workflows/ci.yml/badge.svg)](https://github.com/AlionaVr/Vitube/actions/workflows/ci.yml)

A YouTube clone built with AI: FastAPI, PostgreSQL, React, MinIO, Celery.

- Home feed with categories, search with suggestions, channels with subscriptions and a subscriptions feed.
- Upload with progress; a worker converts the video and makes a thumbnail. Studio lists your videos.
- Watch page: player with seeking, likes, comments with replies, Up next, Save to playlists and Watch later,
  reports.
- Public, unlisted and private videos; a private video can be shared with chosen people.
- Moderation: reports, hidden videos, banned and terminated accounts, an audit log.
- Sign in with an email and password, or [with Google](#sign-in-with-google) once it is set up.

## Quick start

Needs Ubuntu 22.04 or newer, a user with `sudo`, and a free port 80.

```bash
git clone <repo-url> vitube && cd vitube
./install.sh
```

The script:
1. installs Docker Engine and the compose plugin, if missing;
2. creates `.env` with random secrets (an existing `.env` is kept);
3. downloads the demo videos;
4. builds and starts the stack, then waits until the site answers;
5. adds the [demo data](#demo-data);
6. prints the site and API docs URLs, the demo logins and their password.

Re-running it is safe: it applies new code and migrations, and adds demo data that is missing.

Prefix the commands below with `sudo` if your user is not in the `docker` group (the script prints the right form).

| Command | What it does |
|---|---|
| `docker compose ps` | Service status |
| `docker compose logs <service>` | Service logs |
| `docker compose down` | Stop (data is kept) |
| `docker compose down -v` | Stop and **delete all data** |

> Passwords from `.env` are saved into the database and storage on the first start.
> To change them, run `docker compose down -v` first, or the services can't log in.

Other OS: install Docker Engine 28 or newer with Compose 2.39 or newer yourself, then run `./install.sh`.

## Demo data

A fresh site comes with channels, videos, likes, comments, subscriptions, playlists and one report to moderate.
All demo accounts share one password: `DEMO_PASSWORD` in `.env`, random for each install. `install.sh` prints it.

| Account | Channel | Role | On the site |
|---|---|---|---|
| `admin@example.com` | @admin | admin | Moderation with the Accounts and Audit log tabs |
| `moderator@example.com` | @moderator | moderator | Moderation: a spam comment reported under Sintel |
| `openmovies@example.com` | @open-movies | user | Big Buck Bunny and Sintel trailers |
| `nature@example.com` | @nature-clips | user | Flower opening |
| `anna@example.com` | @anna | user | Subscriptions, likes, comments, the public playlist "Open movies" |
| `ben@example.com` | @ben | user | Comments and replies, Watch later |

The videos are three short open-licensed clips: sources and licenses are in [demo-data/](demo-data/README.md).
They are not in git: `install.sh` downloads them and checks their hashes. Without internet the site still works,
and a later `./install.sh` adds them. The worker processes them like any upload.

The seed is the one-shot job `seed` (code: [backend/app/seed.py](backend/app/seed.py)); `install.sh` runs it with
`docker compose run --rm --no-deps seed`. A re-run adds only what is missing. It never changes the role or password
of an existing account, what a moderator removed stays removed, and a banned or terminated demo account does
nothing. If someone signed up with a demo email first, the seed stops and says so.

A re-run finds the demo rows by what people see, such as a video's title, so it doesn't know what the demo accounts
changed: a demo video or playlist its owner renamed is made again, and a like or subscription they took back
returns.

Updating a deployment made before the seed: add `DEMO_PASSWORD=<random, 16+ chars>` to `.env` (for example
`openssl rand -hex 16`), then run `./install.sh` again.

## Configuration

`.env` holds the settings; `install.sh` creates it from [.env.example](.env.example), with a random value for each
`change-me`.

| Variable | Default | |
|---|---|---|
| `HTTP_PORT` | 80 | host port of the site |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `vitube`, random, `vitube` | DB superuser: only migrations use it |
| `POSTGRES_APP_PASSWORD` | random | `vitube_app`, the DB role of the app: data only ([ADR 0010](docs/adr/0010-db-roles.md)) |
| `REDIS_PASSWORD` | random | sessions, rate limits, the task queue |
| `SESSION_SECRET` | random | 32+ chars |
| `COOKIE_SECURE` | false | true when served over HTTPS: cookies then go over HTTPS only |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | empty | [sign-in with Google](#sign-in-with-google); off while empty |
| `GOOGLE_REDIRECT_URI` | `http://localhost/auth/google/callback` | the site's callback page, as set in the Google client |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | `vitube`, random | storage admin: only the setup job uses it |
| `MINIO_APP_PASSWORD` | random | storage user of the app: objects in the bucket only |
| `S3_BUCKET` | `vitube` | |
| `DEMO_PASSWORD` | random | password of the demo accounts, set when they are created; 16+ chars |
| `MAX_UPLOAD_SIZE_MB` | 1024 | file size; checked in the browser, nginx and the API |
| `MAX_VIDEO_DURATION_SEC` | 1800 | longer videos fail with a reason |
| `MAX_VIDEO_HEIGHT` | 720 | taller videos are downscaled |

After a change, run `./install.sh` again.

### Sign-in with Google

Off by default: while `GOOGLE_CLIENT_ID` is empty, the sign-in page has no Google button. To turn it on:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an OAuth client ID of type
   "Web application" (set up the consent screen first if asked).
2. Under "Authorized redirect URIs", add the site's callback page, e.g. `http://localhost/auth/google/callback`
   (with another `HTTP_PORT`, put it in: `http://localhost:8080/...`). Google allows `http` only for `localhost`:
   a server needs a domain and HTTPS (`https://<domain>/auth/google/callback`, and `COOKIE_SECURE=true`).
3. Put the client's ID and secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, and the URI from
   step 2 as `GOOGLE_REDIRECT_URI`. Run `./install.sh` again.

A Google sign-in creates an account without a password. If the email already has a ViTube account, it is refused:
accounts are never joined by email ([ADR 0014](docs/adr/0014-google-sign-in.md)).

## Architecture

```
Browser ──:80──► nginx ─┬─ /             → React static files
                        ├─ /api/*, /docs → api (FastAPI)
                        └─ /media/*      → auth_request → minio
api    ──► postgres, redis, minio; Google (sign-in only)
worker (Celery + ffmpeg) ◄── redis; ──► minio, postgres
one-shot jobs: migrate, minio-init, seed
```

Only nginx is published. The worker and the data services have no internet; the api reaches it for Google sign-in
([ADR 0008](docs/adr/0008-deployment.md)). Each backend module is layered
`router → service → repository → models`, and one access policy decides who may watch a video. The plan, the DB
schema and the reasons for each decision: [docs/plan.md](docs/plan.md), [docs/adr/](docs/adr/README.md).

## Local development

Postgres and Redis run in Docker; the backend runs from the IDE, with a debugger and auto-reload.

1. Add `COMPOSE_FILE=compose.yaml:compose.local.yaml` to `.env`. [compose.local.yaml](compose.local.yaml) opens
   Postgres and Redis on `localhost`. Production (`install.sh`, CI) uses `compose.yaml` only.
2. Copy `.env.local.example` to `.env.local`, put in the passwords from `.env` and a `SESSION_SECRET`.
3. Run:

```bash
docker compose up -d --wait postgres redis
docker compose run --rm --build migrate                          # migrations + app DB role
cd backend
uv run --env-file ../.env.local uvicorn app.main:app --reload    # API on :8000
cd ../frontend
API_PROXY=http://localhost:8000 npm run dev                      # UI on :5173
```

In IntelliJ, the same backend run configuration: `uvicorn app.main:app --reload`, working directory `backend/`,
env file `.env.local`.

## Uploads

Signed in, click **Create** in the header, then pick or drop a video file. The upload starts at once; fill in the
details meanwhile. The worker converts the video to MP4 (H.264/AAC) and makes a thumbnail; the dialog shows the
progress and plays the result. A new video is private until you choose Unlisted or Public. Size, length and height
limits: see [Configuration](#configuration).

Share a private video with someone (API only for now): `POST /api/videos/<id>/access` with `{"handle": "..."}`;
`DELETE /api/videos/<id>/access/<handle>` takes it back. Changes apply to their next request.

Updating a deployment made before uploads existed: add `MINIO_APP_PASSWORD=<random, 8+ chars>` to `.env`, then run
`./install.sh` again.

## Accounts and roles

Sign up on the site with an email and a password. Roles are `user`, `moderator` and `admin`; each has the rights of
the ones before it. Give a role from the command line:

```bash
docker compose exec api python -m app.cli set-role <email> admin
```

It applies at once, also to sessions that are already open.

Moderators and admins open **Moderation** in the account menu (`/moderation`): reports, hidden videos and, for
admins, accounts and the audit log. An admin can also restrict an account from the command line:

```bash
docker compose exec api python -m app.cli set-status <email> banned --by <admin email> --reason "Spam"
```

`banned` blocks sign-in and ends open sessions; `terminated` does the same and hides the channel's videos; `active`
reinstates. `--by` names you in the audit log; `set-role` takes it too, except for the first admin.

Served over HTTPS? Set `COOKIE_SECURE=true` in `.env` and run `./install.sh` again: session cookies then go over
HTTPS only.

Calling the API with curl: POST, PUT, PATCH and DELETE need an `Origin` header with the site's address (CSRF
protection, [ADR 0005](docs/adr/0005-server-sessions.md)). Once signed in, also send the `csrf_token` cookie's value
in `X-CSRF-Token`. With a demo account (put in `DEMO_PASSWORD` from `.env`):

```bash
curl -c jar -b jar -H 'Origin: http://localhost' -H 'Content-Type: application/json' \
  -d '{"email":"anna@example.com","password":"<DEMO_PASSWORD>"}' http://localhost/api/auth/login
curl -b jar -H 'Origin: http://localhost' -H "X-CSRF-Token: $(awk '$6=="csrf_token"{print $7}' jar)" \
  -X POST http://localhost/api/auth/logout
```

## Docs

- Plan and requirements: [docs/plan.md](docs/plan.md)
- Architecture decisions: [docs/adr/](docs/adr/README.md)
- Demo videos: [demo-data/README.md](demo-data/README.md)
- AI tooling: [CLAUDE.md](CLAUDE.md), [.claude/](.claude/)
