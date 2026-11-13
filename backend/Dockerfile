# Two images: app (api and migrate) and worker (the same code plus ffmpeg).
# Images by digest: a tag can be moved to other contents, a digest can't. Dependabot bumps both.

FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /bin/uv
# Bytecode at build time; copy from the cache mount; use the image's Python, never download one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Only the lock files take part, so code changes keep the dependency layer cached.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev

# Shared runtime base: Python and the app user, no build tools.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
# Debian's security fixes ship days before the base image is rebuilt (ADR 0015). No pip: uv builds the
# venv above, and pip's own copies of urllib3 and msgpack lag behind their fixes.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes --quiet pip
# Fixed ids (see USER); no home, no login shell.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app

# api and migrate.
FROM base AS app
# Owned by root: the app user can read its code but not change it.
COPY --from=build /app/.venv .venv
COPY alembic.ini ./
COPY alembic alembic
COPY app app
USER 10001:10001
EXPOSE 8000
# The host comes from UVICORN_HOST (compose.yaml): the api's address on nginx's network, so the only
# peer, and the only one trusted with X-Forwarded-For, is nginx. Without it uvicorn binds 127.0.0.1.
CMD ["uvicorn", "app.main:app", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# The worker: the app plus ffmpeg. Only this image carries it: less to attack in the api.
# ffmpeg goes in before the code, so code changes keep this layer cached. Command: compose.yaml.
FROM base AS worker
# No apt version pins (DL3008): Debian drops old versions from its mirrors; the base is pinned by digest.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# ffmpeg's work files; the worker-scratch volume takes this owner on first mount.
RUN install -d -o 10001 -g 10001 /scratch
COPY --from=build /app/.venv .venv
COPY app app
USER 10001:10001
