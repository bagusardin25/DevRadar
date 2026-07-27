<div align="center">
  <img src="public/logomark_text.webp" alt="DevRadar Logo" width="360" />
  <h1>DevRadar</h1>
  <p><strong>Open-source developer opportunity intelligence</strong> — online hackathons & free AI offers, with multi-tier verification.</p>

  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-emerald.svg" alt="MIT" /></a>
    <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/Contributions-welcome-orange.svg" alt="Contributing" /></a>
  </p>
</div>

---

## What it is

DevRadar aggregates **hackathons / challenges** and **AI free tiers / credits / promos**, then tries to **verify** them against official pages when possible.

| Principle | Meaning |
|-----------|---------|
| **No end-user login** | Browse, filter, bookmark (localStorage), submit URLs without an account |
| **No user API keys** | Visitors never paste OpenAI/X keys into the browser |
| **X is discovery, not truth** | Social posts are Tier-3 signals; official URLs are preferred |
| **Human-in-the-loop** | Admin review queue for publish/reject (Google OAuth, optional) |

This is **not** a claim of perfect accuracy. Listings carry verification status (`verified_active`, `likely_active`, `registration_closed`, …) and prize labels that may say **TBA** when the pool is unknown.

---

## Architecture (short)

```
Browser (React/Vite)  →  FastAPI (/api/v1)  →  PostgreSQL
                              ↓
                     Redis · Celery (fetch queue)
                              ↓
              Connectors: official site, Devpost, MLH, RSS, X (optional)
```

| Piece | Role in local dev |
|-------|-------------------|
| **Docker Compose** (`infra/compose.yaml`) | Postgres **5434**, Redis **6379**, optional MinIO **9000** — *infra only* |
| **API** (host, `:8000`) | FastAPI via `uv run uvicorn` |
| **Worker** (host) | Celery `fetch` queue — submission review, discovery, rechecks |
| **Frontend** (host, `:5173`) | Vite; proxies `/api` and `/health` to the API |

- **Frontend-only** works with offline mock data; the real catalogue needs the API + Postgres.
- **Celery worker required for automatic submission review**: without a `fetch` worker, community submissions stay queued.
- **Seed demo mode** (recommended first run): no OpenAI / no X keys — load curated JSON into Postgres.
- **Object storage default** is local files under `backend/data/raw` (`OBJECT_STORAGE_BACKEND=local`). MinIO is optional if you switch to `s3`.

---

## Quick start (full stack)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose)
- [uv](https://docs.astral.sh/uv/) (Python **3.12+**)
- **Node.js 20+** and npm (CI uses **Node 22**)

### Windows (PowerShell)

```powershell
git clone https://github.com/bagusardin25/DevRadar.git
cd DevRadar
.\scripts\dev.ps1
```

Then **three** terminals:

```powershell
# Terminal A — API
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal B — UI
npm run dev

# Terminal C — Celery fetch/review worker (--pool=solo required on Windows)
cd backend
uv run celery -A app.worker.celery_app worker -Q fetch -l info --pool=solo
```

### macOS / Linux

```bash
git clone https://github.com/bagusardin25/DevRadar.git
cd DevRadar
chmod +x scripts/dev.sh
./scripts/dev.sh
```

Then either three terminals (same commands as above, **omit** `--pool=solo` on Linux/macOS) or:

```bash
make api       # terminal A
make frontend  # terminal B
make worker    # terminal C
```

| URL | Purpose |
|-----|---------|
| http://localhost:5173/ | App |
| http://127.0.0.1:8000/health/ready | API + Postgres + Redis |

### What bootstrap does

`scripts/dev.ps1` / `scripts/dev.sh` (or `make bootstrap`):

1. `docker compose -f infra/compose.yaml up -d`
2. Creates `backend/.env` from `backend/.env.example` (random local secrets; keeps `LLM_PROVIDER=disabled`)
3. `uv sync --all-extras` + `alembic upgrade head`
4. Seeds demo catalogue + default aggregator sources
5. `npm install` if needed

Refresh catalogue after editing seed data:

```bash
cd backend
uv run python scripts/seed_x_mcp_collection.py --update
uv run python scripts/seed_default_sources.py
```

Optional re-fetch of AI offer official pages (rules; LLM if configured):

```bash
cd backend
uv run python scripts/recheck_listings.py --kind ai_offer --limit 25
```

### Environment templates

| File | Purpose |
|------|---------|
| [`backend/.env.example`](backend/.env.example) | Backend settings — copy to **`backend/.env`** (never commit `.env`) |
| [`.env.example`](.env.example) | Optional frontend Vite vars (`VITE_*`) — copy to root `.env` if needed |

Defaults match Compose (Postgres on host port **5434**). Prefer `localhost` for the app URL and OAuth callback host notes in the backend template (`localhost` ≠ `127.0.0.1` for cookies).

### Docker notes

- **Day-to-day dev:** Compose for infra only; API/worker/frontend run on the host (as above).
- **API image:** `docker build -f backend/Dockerfile backend` — production-style image from `uv.lock` (**no** dev extras). Not required for local contribution.

---

## Modes of operation

| Mode | Keys needed | Use case |
|------|-------------|----------|
| **Seed demo** | None (Docker + generated secrets only) | Local try-out, OSS contributors, demos |
| **Ingestion + LLM** | `LLM_API_KEY` (OpenAI-compatible) | Extract structured fields from official pages |
| **X discovery** | `X_BEARER_TOKEN` | Find new candidate URLs (pay-per-use; optional) |
| **Admin review** | Google OAuth + `ADMIN_GOOGLE_EMAILS` | Approve/reject listings, catalogue CRUD |

End users of a **hosted** instance still never need those keys — only the **operator** does.

---

## Features (honest list)

**Public**

- Hackathon catalogue (search, filters, compare, bookmarks)
- AI offer catalogue
- Community **Submit** URL → review queue (AI initial review when worker runs)
- Email alert subscribe (needs operator email provider; default `console`)
- Provenance hints (source tier on cards)

**Operator / admin (behind Google login)**

- Review queue (with AI initial review)
- Catalogue manager (hackathons & AI offers)
- Pipeline viewer
- Sources manager

**Not a production Chrome extension** — the side-panel UI is a **simulator / preview**, not a store package.

---

## CI

PRs to `main` run [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

- Secret scan (Gitleaks)
- Frontend: Node **22** — `npm ci`, `npm run build`, `npm run lint`
- Backend: Python **3.12**, Postgres **16**, Redis **7** — `ruff check`, `alembic upgrade head`, `pytest`

Local checks match [CONTRIBUTING.md](CONTRIBUTING.md#checks-before-a-pr).

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** and **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)**.

Preferred ways to add opportunities:

1. In-app **Submit** (URL → review pipeline)
2. PR against curated seed: `data/manual-collection/seed_listings.json` (not `src/data/mockData.ts`)
3. Connector / docs / bugfix PRs

---

## Security

See **[SECURITY.md](SECURITY.md)**. Never commit `.env` or live API keys.

---

## License

[MIT](LICENSE) — Copyright (c) 2026 DevRadar Contributors
