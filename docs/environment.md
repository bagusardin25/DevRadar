# DevRadar Backend Environment Variables

Copy `backend/.env.example` → `backend/.env` and fill values for your machine.

Postgres in local Compose listens on **host port 5434** (avoids clashing with a local Windows PostgreSQL on 5433).

```bash
# Start infra
docker compose -f infra/compose.yaml up -d

# Backend
cd backend
cp .env.example .env   # then edit
uv sync --all-extras   # or use existing .venv
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

---

## Variable reference

### Required for local API (Tasks 1–6)

| Variable | Example / default | Required? | Notes |
|---|---|---|---|
| `APP_ENV` | `development` | Yes | `development` / `test` / `production` |
| `API_BASE_PATH` | `/api/v1` | Yes | Public API prefix |
| `FRONTEND_URL` | `http://localhost:5173` | Yes | OAuth redirect target + CORS peer |
| `CORS_ORIGINS` | `http://localhost:5173` | Yes | Comma-separated or JSON list |
| `DATABASE_URL` | `postgresql+asyncpg://devradar:devradar@127.0.0.1:5434/devradar` | Yes | Async SQLAlchemy URL |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Yes | Sessions, rate limits, Celery broker |
| `SESSION_SECRET` | long random string (≥32 chars) | Yes | HMAC for IP hashes / session material |
| `EMAIL_ENCRYPTION_KEY` | any long secret | Yes* | Fernet-derived key for optional emails |
| `EMAIL_HMAC_KEY` | long random string (≥32 chars) | Yes* | Email lookup hash |

\*Required by settings even if you are not using email alerts yet.

### Object storage (Task 6)

| Variable | Example | Required? | Notes |
|---|---|---|---|
| `OBJECT_STORAGE_BACKEND` | `local` | Yes | `local` (dev), `s3` (MinIO/AWS), `memory` (tests) |
| `OBJECT_STORAGE_LOCAL_PATH` | `./data/raw` | If `local` | Directory for content-addressed blobs |
| `OBJECT_STORAGE_ENDPOINT` | `http://localhost:9000` | If `s3` | MinIO endpoint |
| `OBJECT_STORAGE_BUCKET` | `devradar-raw` | If `s3` | Bucket name |
| `OBJECT_STORAGE_ACCESS_KEY` | `devradar` / MinIO user | If `s3` | |
| `OBJECT_STORAGE_SECRET_KEY` | MinIO password | If `s3` | **Secret** |
| `OBJECT_STORAGE_REGION` | `us-east-1` | If `s3` | |

### Fetch policy (optional overrides)

| Variable | Default | Notes |
|---|---|---|
| `FETCH_TIMEOUT_SECONDS` | `20` | Per-request timeout |
| `FETCH_MAX_BYTES` | `5242880` | 5 MiB response cap |
| `FETCH_MAX_REDIRECTS` | `5` | Hop limit |

### Admin GitHub OAuth (Task 5 — needed for admin UI login)

| Variable | Required to use admin? | Notes |
|---|---|---|
| `GITHUB_CLIENT_ID` | Yes for real OAuth | GitHub OAuth App |
| `GITHUB_CLIENT_SECRET` | Yes for real OAuth | **Secret** |
| `ADMIN_GITHUB_IDS` | Yes | Comma-separated **numeric** GitHub user IDs on allowlist |

Callback (local): `http://127.0.0.1:8000/api/v1/admin/auth/github/callback`  
Register that URL on the GitHub OAuth App.

### Email alerts (Task 10 — later)

| Variable | Default | Notes |
|---|---|---|
| `EMAIL_PROVIDER` | `console` | `console` logs only; swap for SES/etc later |
| `EMAIL_FROM` | `alerts@example.test` | From address |

### LLM extraction (structured fields only — not web search)

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `disabled` | `openai` enables Chat Completions fill-in after rules |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model id |
| `LLM_API_KEY` | _(empty)_ | **Secret**; `OPENAI_API_KEY` accepted as alias |
| `OPENAI_API_KEY` | _(empty)_ | Alias for `LLM_API_KEY` if that is empty |

### X / Twitter discovery (Task 11 — later)

| Variable | Default | Notes |
|---|---|---|
| `X_BEARER_TOKEN` | _(empty)_ | **Secret**; only for live/X connector |

---

## What you should fill **now** (minimal local backend)

1. Generate secrets (PowerShell example):

```powershell
# 32+ random bytes as base64
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

Set:
- `SESSION_SECRET`
- `EMAIL_ENCRYPTION_KEY`
- `EMAIL_HMAC_KEY`

2. Keep Compose defaults for DB/Redis/MinIO unless ports conflict.

3. Leave OAuth/LLM/X empty until you need admin login or later tasks.

4. Use `OBJECT_STORAGE_BACKEND=local` so MinIO is optional for fetch storage tests.

---

## Secrets that must **never** go to the browser worker

When a Playwright container is added, do **not** inject:

- `DATABASE_URL`, `REDIS_URL`
- `SESSION_SECRET`, `EMAIL_*`, `GITHUB_CLIENT_SECRET`
- `LLM_API_KEY`, `X_BEARER_TOKEN`, `OBJECT_STORAGE_SECRET_KEY`

(See `app.ingestion.browser.BROWSER_WORKER_FORBIDDEN_ENV`.)

---

## Celery worker (Task 6)

```bash
cd backend
uv run celery -A app.worker.celery_app.celery_app worker -Q fetch -l info
# later, isolated:
# uv run celery -A app.worker.celery_app.celery_app worker -Q browser -l info
```
