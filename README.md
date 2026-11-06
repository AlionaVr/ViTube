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
2. Copy `.env.local.example` to `.env.local` and put in the passwords from `.env`.
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

## Docs

- Plan and requirements: [docs/plan.md](docs/plan.md)
- Architecture decisions: [docs/adr/](docs/adr/README.md)
- AI tooling: [CLAUDE.md](CLAUDE.md), [.claude/](.claude/)
