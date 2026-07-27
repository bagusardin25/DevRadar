#!/usr/bin/env bash
# DevRadar local bootstrap (macOS / Linux)
# Usage (from repo root):
#   ./scripts/dev.sh              # infra + migrate + seed
#   ./scripts/dev.sh --skip-seed  # infra + migrate only
#   ./scripts/dev.sh --api        # also start uvicorn (blocks)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_SEED=0
START_API=0
for arg in "$@"; do
  case "$arg" in
    --skip-seed) SKIP_SEED=1 ;;
    --api) START_API=1 ;;
    -h|--help)
      cat <<'EOF'
DevRadar local bootstrap

  ./scripts/dev.sh              Start Docker infra, ensure backend/.env, migrate, seed demo data
  ./scripts/dev.sh --skip-seed  Same without catalogue seed
  ./scripts/dev.sh --api        After bootstrap, run API on :8000 (blocking)

Typical three-terminal flow after first bootstrap:
  Terminal A:  cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  Terminal B:  npm run dev
  Terminal C:  cd backend && uv run celery -A app.worker.celery_app worker -Q fetch -l info
EOF
      exit 0
      ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }

step "Checking Docker"
if ! docker info >/dev/null 2>&1; then
  echo "Docker engine is not running. Start Docker, then re-run this script." >&2
  exit 1
fi

step "Starting Postgres + Redis + MinIO (infra/compose.yaml)"
docker compose -f infra/compose.yaml up -d

step "Waiting for Postgres"
for i in $(seq 1 30); do
  if docker compose -f infra/compose.yaml exec -T postgres pg_isready -U devradar >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [ "$i" -eq 30 ]; then
    echo "Postgres did not become ready in time." >&2
    exit 1
  fi
done

if [ ! -f backend/.env ]; then
  step "Creating backend/.env from backend/.env.example"
  cp backend/.env.example backend/.env
  # shellcheck disable=SC2002
  SECRET1=$(openssl rand -base64 48 2>/dev/null || head -c 48 /dev/urandom | base64)
  SECRET2=$(openssl rand -base64 48 2>/dev/null || head -c 48 /dev/urandom | base64)
  SECRET3=$(openssl rand -base64 48 2>/dev/null || head -c 48 /dev/urandom | base64)
  sed -i.bak \
    -e "s|SESSION_SECRET=.*|SESSION_SECRET=${SECRET1}|" \
    -e "s|EMAIL_ENCRYPTION_KEY=.*|EMAIL_ENCRYPTION_KEY=${SECRET2}|" \
    -e "s|EMAIL_HMAC_KEY=.*|EMAIL_HMAC_KEY=${SECRET3}|" \
    -e "s|^LLM_PROVIDER=.*|LLM_PROVIDER=disabled|" \
    backend/.env
  rm -f backend/.env.bak
  echo "  Wrote local secrets; LLM_PROVIDER=disabled (seed demo works without OpenAI)."
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

step "Installing backend deps (uv)"
(
  cd backend
  uv sync --all-extras
  step "Running migrations"
  uv run alembic upgrade head
  if [ "$SKIP_SEED" -eq 0 ]; then
    step "Seeding demo catalogue (idempotent by slug)"
    uv run python scripts/seed_listings.py
    step "Seeding default aggregator sources (Devpost/MLH/HackerEarth)"
    uv run python scripts/seed_default_sources.py
  fi
)

if [ ! -d node_modules ]; then
  step "Installing frontend deps (npm)"
  npm install
fi

cat <<'EOF'

Bootstrap complete.

Next:
  API:      cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  Frontend: npm run dev
  Worker:   cd backend && uv run celery -A app.worker.celery_app worker -Q fetch -l info
  Health:   http://127.0.0.1:8000/health/ready
  App:      http://localhost:5173/

Demo data: data/manual-collection/seed_listings.json
Refresh:   cd backend && uv run python scripts/seed_listings.py --update
EOF

if [ "$START_API" -eq 1 ]; then
  step "Starting API on :8000"
  cd backend
  exec uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi
