# DevRadar developer shortcuts (requires Docker + uv + Node)
# Windows users can use:  .\scripts\dev.ps1

.PHONY: help up down bootstrap seed seed-update seed-sources recheck-offers api worker frontend test-backend lint-backend lint-frontend build-frontend health

help:
	@echo "DevRadar targets:"
	@echo "  make bootstrap     Docker up + migrate + seed demo catalogue"
	@echo "  make up / down     Start/stop infra (Postgres, Redis, MinIO)"
	@echo "  make seed          Insert demo listings (skip existing slugs)"
	@echo "  make seed-update   Refresh prize labels & core fields on existing slugs"
	@echo "  make seed-sources  Seed Devpost/MLH/HackerEarth source registry"
	@echo "  make recheck-offers  Re-fetch AI offer official URLs (rules/LLM extract)"
	@echo "  make api           Run FastAPI on :8000"
	@echo "  make worker        Run Celery fetch/review worker"
	@echo "  make frontend      Run Vite on :5173"
	@echo "  make test-backend  pytest (needs infra up)"
	@echo "  make lint-backend  ruff check app tests"
	@echo "  make lint-frontend oxlint"
	@echo "  make build-frontend  production frontend build"
	@echo "  make health        curl /health/ready"

up:
	docker compose -f infra/compose.yaml up -d

down:
	docker compose -f infra/compose.yaml down

bootstrap:
	@bash scripts/dev.sh

seed:
	cd backend && uv run python scripts/seed_x_mcp_collection.py

seed-update:
	cd backend && uv run python scripts/seed_x_mcp_collection.py --update

seed-sources:
	cd backend && uv run python scripts/seed_default_sources.py

recheck-offers:
	cd backend && uv run python scripts/recheck_listings.py --kind ai_offer --limit 25

api:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd backend && uv run celery -A app.worker.celery_app worker -Q fetch -l info

frontend:
	npm run dev

test-backend:
	cd backend && uv run pytest -q

lint-backend:
	cd backend && uv run ruff check app tests

lint-frontend:
	npm run lint

build-frontend:
	npm run build

health:
	curl -sS http://127.0.0.1:8000/health/ready | python -m json.tool || curl -sS http://127.0.0.1:8000/health/ready
