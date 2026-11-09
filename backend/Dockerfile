# Two images: app (api and migrate) and worker (the same code plus ffmpeg).

FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv
# Bytecode at build time; copy from the cache mount; use the image's Python, never download one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Only the lock files take part, so code changes keep the dependency layer cached.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev

# Shared runtime base: Python and the app user, no build tools.
FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
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
# Trusts X-Forwarded-For from any peer: only nginx (network "web") and our own services reach the api.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# The worker: the app plus ffmpeg. Only this image carries it: less to attack in the api.
# ffmpeg goes in before the code, so code changes keep this layer cached. Command: compose.yaml.
FROM base AS worker
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# ffmpeg's work files; the worker-scratch volume takes this owner on first mount.
RUN install -d -o 10001 -g 10001 /scratch
COPY --from=build /app/.venv .venv
COPY app app
USER 10001:10001
