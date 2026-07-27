# syntax=docker/dockerfile:1
#
# Secure API image (no secrets in layers; non-root runtime).
#
#   docker build -f backend/Dockerfile -t devradar-api:local backend
#
# Inject configuration at *run* time (never bake .env into the image):
#
#   docker run --rm -p 8000:8000 --env-file /path/to/production.env devradar-api:local
#
# Local day-to-day dev still uses Compose for infra + host-run API (see README).

# -----------------------------------------------------------------------------
# Builder: resolve dependencies from the lockfile only
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dependency layer first for cache efficiency. Project code is installed later.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN uv sync --frozen --no-dev \
    && rm -rf /root/.cache /tmp/*

# -----------------------------------------------------------------------------
# Runtime: slim image, non-root user, no build tooling required
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    APP_ENV=production \
    # Safe defaults; override at run time. Do not put secrets here.
    PYTHONPATH="/app"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --home /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/raw \
    && chown -R app:app /app

# Copy only the virtualenv and application code from the builder (no uv binary).
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=app:app /app/alembic /app/alembic
COPY --from=builder --chown=app:app /app/app /app/app
COPY --from=builder --chown=app:app /app/scripts /app/scripts
COPY --from=builder --chown=app:app /app/pyproject.toml /app/pyproject.toml

USER app

EXPOSE 8000

# Liveness only (no DB/Redis required). Readiness is /health/ready once wired.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/live || exit 1

# Bind all interfaces inside the container; publish selectively on the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
