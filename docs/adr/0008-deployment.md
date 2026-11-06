# 0008. Deploy: `install.sh` + Docker Compose

**Status:** accepted · 2026-11-04

**Context.** Reviewers deploy on a clean Ubuntu with one command. Register → upload → watch → like → comment must work
right away.

**Decision.** `./install.sh` (safe to re-run):

1. Installs Docker Engine and the compose plugin from Docker's apt repo if missing.
2. Creates `.env` from `.env.example` with random secrets. Never overwrites an existing `.env`.
3. Runs `docker compose up -d --build --wait`:
    - services: nginx, api, worker, postgres, redis, minio;
    - one-shot jobs: `migrate`, `minio-init`, `seed`.
4. Prints the site URL, Swagger URL and demo logins.

Only port 80 is exposed. All services have healthchecks, `restart: unless-stopped`, and named volumes.

Containers are hardened:

- non-root users, `no-new-privileges`, all capabilities dropped (data services keep only what their entrypoint needs);
- read-only root FS for our containers;
- networks: `edge` (nginx only, the published port), internal `web` (nginx ↔ api) and internal `data`
  (backend ↔ Postgres, Redis, MinIO). The backend and data have no internet access.

Local development adds `compose.local.yaml` (DB ports on localhost); `install.sh` never uses it.

**Alternatives.** Native apt + systemd: no Docker, but fragile across Ubuntu versions.

**Consequences.**

- ➕ Same setup on reviewer VM, dev machine and CI.
- ➖ The first build takes a few minutes.
