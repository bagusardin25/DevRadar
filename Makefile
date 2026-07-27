# DevRadar developer shortcuts (requires Docker + uv + Node).
# Windows: .\scripts\dev.ps1 for bootstrap; .\scripts\check.ps1 for CI-parity checks.
# Command matrix is documented in CONTRIBUTING.md — keep this file in sync with CI.

.PHONY: help up down bootstrap seed seed-update seed-sources recheck-offers \
	api worker frontend \
	sync-backend migrate lint-backend test-backend check-backend \
	lint-frontend build-frontend check-frontend \
	check clean health

help:
	@echo "DevRadar targets (aligned with CI where noted):"
	@echo "  make bootstrap       Docker up + uv sync + migrate + seed"
	@echo "  make up / down       Start/stop infra (Postgres, Redis; MinIO via profile)"
	@echo "  make up-minio        Infra + MinIO object-storage profile"
	@echo "  make docker-build    Build API image (context=backend/, no secrets)"
	@echo "  make sync-backend    uv sync --all-extras --frozen  (CI install)"
	@echo "  make migrate         alembic upgrade head           (CI migrate)"
	@echo "  make lint-backend    ruff check app tests           (CI lint)"
	@echo "  make test-backend    pytest                         (CI test; needs infra)"
	@echo "  make check-backend   lint + migrate + test          (CI backend job)"
	@echo "  make lint-frontend   npm run lint                   (CI lint)"
	@echo "  make build-frontend  npm run build                  (CI build)"
	@echo "  make check-frontend  build + lint                   (CI frontend job)"
	@echo "  make check           check-frontend + check-backend (full local CI gate)"
	@echo "  make seed / seed-update / seed-sources / recheck-offers"
	@echo "  make api / worker / frontend / health / clean"

# --- Infra & bootstrap -------------------------------------------------------

up:
	docker compose -f infra/compose.yaml up -d

up-minio:
	docker compose -f infra/compose.yaml --profile object-storage up -d

down:
	docker compose -f infra/compose.yaml down

# Build context is backend/ so root monorepo files never enter the daemon.
docker-build:
	docker build -f backend/Dockerfile -t devradar-api:local backend

bootstrap:
	@bash scripts/dev.sh

seed:
	cd backend && uv run python scripts/seed_listings.py

seed-update:
	cd backend && uv run python scripts/seed_listings.py --update

seed-sources:
	cd backend && uv run python scripts/seed_default_sources.py

recheck-offers:
	cd backend && uv run python scripts/recheck_listings.py --kind ai_offer --limit 25

# --- Runtime -----------------------------------------------------------------

api:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && uv run celery -A app.worker.celery_app worker -Q fetch -l info

frontend:
	npm run dev

health:
	curl -sS http://127.0.0.1:8000/health/ready | python -m json.tool || curl -sS http://127.0.0.1:8000/health/ready

# --- Lint / test / build / migrate (CI parity) -------------------------------

sync-backend:
	cd backend && uv sync --all-extras --frozen

migrate:
	cd backend && uv run alembic upgrade head

lint-backend:
	cd backend && uv run ruff check app tests

test-backend:
	cd backend && uv run pytest

check-backend: lint-backend migrate test-backend

lint-frontend:
	npm run lint

build-frontend:
	npm run build

# Same order as .github/workflows/ci.yml frontend job (after npm ci).
check-frontend: build-frontend lint-frontend

# Full contributor gate (infra must already be up for backend tests).
# Delegates to scripts/check.sh so Make and the shell script stay identical.
check:
	@bash scripts/check.sh

clean:
	@bash scripts/clean.sh
