# 0015. Supply chain: pinned inputs, Dependabot, CI scanners

**Status:** accepted · 2026-11-13

**Context.** The stack pulls code from many places: base images, Python and npm packages, GitHub Actions. A tag can be
moved to other contents (in March 2026 trivy-action's tags were moved to code that stole CI secrets), and fixes for
known CVEs have to reach us. Reviewers deploy the same files on a clean VM, so whatever CI checks is what they get.

**Decision.**

- **Pinned inputs.** Images by `tag@sha256:<index digest>` (Dockerfiles and `compose.yaml`; the index keeps arm64
  working). Libraries by their lock files (`uv.lock`, `package-lock.json`). Actions by commit SHA with the version in
  a comment. Swagger UI comes from the npm lock, served by nginx: no CDN at runtime.
- **Dependabot** (`.github/dependabot.yml`) proposes updates weekly for all of them. A release waits 7 days first.
  Image majors are never proposed: Python, Node and Postgres majors are planned moves (a Postgres major needs a data
  migration).
- **Scanners in CI**, blocking:
    - hadolint on the Dockerfiles; an accepted rule is ignored on its line, with the reason above;
    - Trivy on the lock files and on our images (backend, worker, nginx): HIGH or CRITICAL with a released fix
      fails the build;
    - squawk on the SQL of new migrations (`scripts/lint_migrations.py`, pull requests): long locks, unsafe changes.
      Model choices are excluded in `backend/.squawk.toml`, with reasons.
- **Third-party images** (Postgres, Redis, MinIO) are scanned as a report only: we can't fix them, and their fixes
  come with a new digest. Postgres's `gosu` is skipped: the container starts as `postgres` (ADR 0008).
- The nginx image runs `apk upgrade` at build: its base is rebuilt less often than Alpine ships fixes.
- **Published images** (ADR 0008). The `publish` job runs on pushes to `main` after every other job passed. It
  loads the images the `stack` job tested (their IDs recorded before any test tool ran), pushes them and signs
  each digest with cosign, keyless: the certificate names this workflow and the commit. The Docker Hub token lives
  in the `dockerhub` environment, for `main` only, and never meets the test tools. `install.sh` verifies the
  signature with a digest-pinned cosign image and tags the checked digest; on any doubt it builds. A stolen
  Docker Hub token can move a tag, but not make a signature. Compose sets our services' users, so no image can
  pick root.

**Alternatives.**

- Renovate: more options (e.g. auto-merge), but one more app with write access; Dependabot is built into GitHub.
- Grype or Docker Scout instead of Trivy: similar results; Trivy also scans lock files with one tool.
- Blocking on third-party images: CI would stay red until upstream releases, with nothing to change on our side.

**Consequences.**

- ➕ A build uses the reviewed inputs only; a new CVE with a fix in our code or images stops the PR.
- ➖ A CVE published overnight can fail an unrelated PR until the fix is taken (a Dependabot PR or `apk upgrade`).
- ➖ The nginx image is not bit-for-bit reproducible: `apk upgrade` takes the packages of the build day.
- ➖ Installing a published commit needs Sigstore's servers (ghcr.io, its trust root); without them it builds.
