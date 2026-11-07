# ViTube

[![CI](https://github.com/AlionaVr/Vitube/actions/workflows/ci.yml/badge.svg)](https://github.com/AlionaVr/Vitube/actions/workflows/ci.yml)

A YouTube clone built with AI: FastAPI, PostgreSQL, React, MinIO, Celery.

> Work in progress. Demo accounts and the config reference will be added as stages land.

## Quick start

Needs Ubuntu 22.04 or newer, a user with `sudo`, and a free port 80.

```bash
git clone <repo-url> vitube && cd vitube
./install.sh
```

The script:
1. installs Docker Engine and the compose plugin, if missing;
2. creates `.env` with random secrets (an existing `.env` is kept);
3. builds and starts the stack, then waits until the site answers;
4. prints the site and API docs URLs.

Re-running it is safe: it applies new code and migrations.

Prefix the commands below with `sudo` if your user is not in the `docker` group (the script prints the right form).

| Command | What it does |
|---|---|
| `docker compose ps` | Service status |
| `docker compose logs <service>` | Service logs |
| `docker compose down` | Stop (data is kept) |
| `docker compose down -v` | Stop and **delete all data** |

> Passwords from `.env` are saved into the database and storage on the first start.
> To change them, run `docker compose down -v` first, or the services can't log in.

Other OS: install Docker with Compose 2.39 or newer yourself, then run `./install.sh`.

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

## Accounts and roles

Sign up on the site with an email and a password. Roles are `user`, `moderator` and `admin`; each has the rights of
the ones before it. Give a role from the command line:

```bash
docker compose exec api python -m app.cli set-role <email> admin
```

It applies at once, also to sessions that are already open.

Served over HTTPS? Set `COOKIE_SECURE=true` in `.env` and run `./install.sh` again: session cookies then go over
HTTPS only.

Calling the API with curl: POST, PUT, PATCH and DELETE need an `Origin` header with the site's address (CSRF
protection, [ADR 0005](docs/adr/0005-server-sessions.md)). Once signed in, also send the `csrf_token` cookie's value
in `X-CSRF-Token`:

```bash
curl -c jar -b jar -H 'Origin: http://localhost' -H 'Content-Type: application/json' \
  -d '{"email":"anna@example.com","password":"correct horse"}' http://localhost/api/auth/login
curl -b jar -H 'Origin: http://localhost' -H "X-CSRF-Token: $(awk '$6=="csrf_token"{print $7}' jar)" \
  -X POST http://localhost/api/auth/logout
```

## Docs

- Plan and requirements: [docs/plan.md](docs/plan.md)
- Architecture decisions: [docs/adr/](docs/adr/README.md)
- AI tooling: [CLAUDE.md](CLAUDE.md), [.claude/](.claude/)
