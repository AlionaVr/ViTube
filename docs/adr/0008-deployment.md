# 0008. Deploy: `install.sh` + Docker Compose

**Status:** accepted · 2026-11-04

**Context.** Reviewers deploy on a clean Ubuntu with one command. Register → upload → watch → like → comment must work
right away.

**Decision.** `./install.sh` (safe to re-run):

1. Installs Docker Engine and the compose plugin from Docker's apt repo if missing.
2. Creates `.env` from `.env.example` with random secrets. Never overwrites an existing `.env`.
3. Downloads the demo videos (`demo-data/download.py`, pinned hashes): they aren't in git, and the backend has no
   internet. A failed download only warns; the site works without them.
4. Runs `docker compose up -d --build --wait`:
    - services: nginx, api, worker, postgres, redis, minio;
    - one-shot jobs: `migrate`, `minio-init`.
5. Runs the one-shot `seed` job (`docker compose run --rm --no-deps seed`): demo accounts and videos. Safe to re-run.
   *(Amended 2026-11-12: was part of `up`, but `up --wait` fails when a job that nothing depends on exits fast, even
   with code 0.)*
6. Prints the site URL, Swagger URL, demo logins and their password.

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
