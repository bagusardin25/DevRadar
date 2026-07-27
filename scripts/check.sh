#!/usr/bin/env bash
# Mirror GitHub Actions CI gates (frontend + backend).
# Prerequisites: Docker infra up (Postgres :5434, Redis :6379), backend deps installed.
# Usage (repo root):  ./scripts/check.sh   or   make check

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { printf '\n==> %s\n' "$1"; }

# --- Frontend (same as ci.yml frontend job after npm ci) ---
step "Frontend build (npm run build)"
npm run build

step "Frontend lint (npm run lint)"
npm run lint

# --- Backend (same as ci.yml backend job after uv sync) ---
cd backend

step "Backend lint (uv run ruff check app tests)"
uv run ruff check app tests

step "Backend migrate (uv run alembic upgrade head)"
uv run alembic upgrade head

step "Backend test (uv run pytest)"
uv run pytest

echo
echo "All CI-parity checks passed."
