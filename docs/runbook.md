# DevRadar Backend Operations Runbook

## Local stack

```bash
docker compose -f infra/compose.yaml up -d
cd backend
cp .env.example .env   # fill secrets — see docs/ENV_SETUP.md
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# optional workers
uv run celery -A app.worker.celery_app.celery_app worker -Q fetch -l info
```

Health: `GET /health/live`, `GET /health/ready`

## Migrations

```bash
cd backend
uv run alembic upgrade head          # apply
uv run alembic downgrade -1          # rollback one revision
uv run alembic history               # list revisions
uv run alembic current               # show head on DB
```

**Production deploy order:** stop workers → migrate → deploy API → start workers.

## Rollback

1. Redeploy previous API image/commit.
2. `alembic downgrade <previous_revision>` only if the new migration is safe to reverse.
3. Re-enable sources gradually.

## PostgreSQL backup / restore (outline)

```bash
# backup
docker compose -f infra/compose.yaml exec -T postgres \
  pg_dump -U devradar devradar > backup.sql

# restore (destructive)
docker compose -f infra/compose.yaml exec -T postgres \
  psql -U devradar devradar < backup.sql
```

In production use managed backups + PITR; test restore before go-live.

## Queue drain

```bash
# inspect Redis queue depth
redis-cli LLEN devradar:queue:fetch

# stop producers (scheduler/API) then let workers empty queues
# purge only in emergency (loses jobs):
# celery -A app.worker.celery_app.celery_app purge
```

## Disable a source (incident)

```http
PATCH /api/v1/admin/sources/{id}
{ "enabled": false }
```

Or set `enabled=false` on `source_queries`. Scheduler skips disabled rows.

## Kill switches

| Control | How |
|---|---|
| Live discovery | Rate limits + opt-in; disable route at gateway if needed |
| X discovery | Clear `X_BEARER_TOKEN`; disable `x_recent_search` sources |
| LLM | `LLM_PROVIDER=disabled` |
| Ingestion | Disable sources or stop Celery workers |

## Incident checklist

1. Confirm `/health/ready` (Postgres + Redis).
2. Check recent `crawl_runs` / `GET /admin/crawl-runs`.
3. Disable noisy sources.
4. Inspect logs for secrets (must not contain emails, tokens, raw bodies).
5. Roll back or fix forward; postmortem with trace IDs.
