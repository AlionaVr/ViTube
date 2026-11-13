# 0008. Deploy: `install.sh` + Docker Compose

**Status:** accepted · 2026-11-04

**Context.** Reviewers deploy on a clean Ubuntu with one command. Register → upload → watch → like → comment must work
right away.

**Decision.** `./install.sh` (safe to re-run):

1. Installs Docker Engine and the compose plugin from Docker's apt repo if missing.
2. Creates `.env` from `.env.example` with random secrets. Never overwrites an existing `.env`.
3. Downloads the demo videos (`demo-data/download.py`, pinned hashes): they aren't in git, and the backend has no
   internet. A failed download only warns; the site works without them.
4. Runs `docker compose up -d --wait`. If CI published the images of the checked-out commit
   (`docker.io/<ns>/vitube-{backend,worker,nginx}:sha-<commit>`) and the engine is amd64 and `backend`, `frontend`,
   `nginx` have no local changes, it pulls them, checks that CI signed each one for this commit (ADR 0015) and tags
   the checked digests with the local names `compose.yaml` uses. Otherwise it builds them (`--build`). CI pushes
   the images that passed the `stack` job, once every check passed, on each push to `main`.
   *(Amended 2026-11-13: always built them.)*
    - services: nginx, api, worker, postgres, redis, minio;
    - one-shot jobs: `minio-perms`, `migrate`, `minio-init`.
5. Runs the one-shot `seed` job (`docker compose run --rm --no-deps seed`): demo accounts and videos. Safe to re-run.
   *(Amended 2026-11-12: was part of `up`, but `up --wait` fails when a job that nothing depends on exits fast, even
   with code 0.)*
6. Prints the site URL, Swagger URL, demo logins and their password.

Only port 80 is exposed. All services have healthchecks, `restart: unless-stopped`, and named volumes.

Containers are hardened:

- non-root users, `no-new-privileges`, all capabilities dropped. Postgres, Redis and MinIO start as their own
  users; the one-shot `minio-perms` job (root with `CHOWN` only, no network) hands the MinIO volume to its user.
  *(Amended 2026-11-13: data services started as root and kept the capabilities to chown their data and drop to
  their user, incl. `DAC_READ_SEARCH` for Postgres.)*
- read-only root FS for our containers;
- networks: `edge` (nginx only, the published port), internal `web` (nginx ↔ api) and internal `data`
  (backend ↔ Postgres, Redis, MinIO). The worker and data have no internet access. *(Amended 2026-11-12: the api
  joins `oauth-egress` for Google sign-in, ADR 0014. It is a plain bridge network: Docker can't limit it to
  Google's hosts, so the api can reach any host. A known exception, accepted for now. `install.sh` requires Docker
  Engine 28+: older engines let hosts on the LAN route to the api through this network, past nginx.)*

Local development adds `compose.local.yaml` (DB ports on localhost); `install.sh` never uses it.

**Alternatives.**

- Native apt + systemd: no Docker, but fragile across Ubuntu versions.
- A tag variable in `compose.yaml` for the published images: a later plain `docker compose up` lacks it and builds
  again.

**Consequences.**

- ➕ Same setup on reviewer VM, dev machine and CI.
- ➕ A published commit installs without a build: no PyPI, npm or apt downloads.
- ➖ Otherwise (a branch, local changes, arm64) the first build takes a few minutes.
