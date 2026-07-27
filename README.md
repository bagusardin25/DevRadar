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
| **Human-in-the-loop** | Admin review queue for publish/reject (GitHub OAuth, optional) |

This is **not** a claim of perfect accuracy. Listings carry verification status (`verified_active`, `likely_active`, `registration_closed`, …) and prize labels that may say **TBA** when the pool is unknown.

---

## Architecture (short)

```
Browser (React/Vite)  →  FastAPI (/api/v1)  →  PostgreSQL
                              ↓
                     Redis · Celery workers (optional)
                              ↓
              Connectors: official site, Devpost, MLH, RSS, X (optional)
```

- **Frontend-only** works with offline mock data, but the real catalogue needs the backend.
- **Celery worker required for automatic submission review**: without a `fetch` worker, community submissions remain queued for admin follow-up.
- **Seed demo mode** (recommended first run): no OpenAI / no X keys — load curated JSON into Postgres.

---

## Quick start (full stack)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Postgres **5434**, Redis **6379**, optional MinIO)
- [uv](https://docs.astral.sh/uv/) (Python 3.12+)
- Node.js 20+ and npm

### Windows (PowerShell)

```powershell
git clone https://github.com/bagusardin25/DevRadar.git
cd DevRadar
.\scripts\dev.ps1
```

Then three terminals:

```powershell
# Terminal A — API
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal B — UI
npm run dev
```

```powershell
# Terminal C - submission fetch and AI review worker
cd backend
uv run celery -A app.worker.celery_app worker -Q fetch -l info --pool=solo
```

- App: http://localhost:5173/  
- API health: http://127.0.0.1:8000/health/ready  

### macOS / Linux

```bash
git clone https://github.com/bagusardin25/DevRadar.git
cd DevRadar
chmod +x scripts/dev.sh
./scripts/dev.sh
# then: make api   and   make frontend
```

### What `dev.ps1` / `dev.sh` does

1. `docker compose -f infra/compose.yaml up -d`
2. Creates `backend/.env` from example (random local secrets, `LLM_PROVIDER=disabled`)
3. `uv sync` + `alembic upgrade head`
4. Seeds demo catalogue from `data/manual-collection/seed_listings.json`
5. `npm install` if needed

Refresh catalogue after editing seed data:

```bash
cd backend
uv run python scripts/seed_x_mcp_collection.py --update
uv run python scripts/seed_default_sources.py   # Devpost / MLH / HackerEarth registry
```

Public cards show **completeness** badges (`PRIZE TBA`, `WEAK URL`, `CLOSING SOON`, field % score). Past deadlines auto-transition to `registration_closed` / `expired` on catalogue reads.

Refresh AI offer pages from the live web (rules extract; optional LLM):

```bash
cd backend
uv run python scripts/recheck_listings.py --kind ai_offer --limit 25
```

Env template: `backend/.env.example` (copy to `backend/.env`).  
Optional deeper notes may live in a local `docs/` folder (gitignored — not part of the published repo).

---

## Modes of operation

| Mode | Keys needed | Use case |
|------|-------------|----------|
| **Seed demo** | None (Docker + secrets only) | Local try-out, OSS contributors, demos |
| **Ingestion + LLM** | `LLM_API_KEY` (OpenAI-compatible) | Extract structured fields from official pages |
| **X discovery** | `X_BEARER_TOKEN` or X MCP | Find new candidate URLs (pay-per-use; optional) |
| **Admin review** | GitHub OAuth + `ADMIN_GITHUB_IDS` | Approve/reject listings |

End users of a **hosted** instance still never need those keys — only the **operator** does.

---

## Features (honest list)

**Public**

- Hackathon catalogue (search, filters, compare, bookmarks)
- AI offer catalogue
- Community **Submit** URL → review queue
- Email alert subscribe (needs operator email provider; default `console`)
- Provenance hints (source tier on cards)

**Operator / admin (behind GitHub login)**

- Review queue
- Pipeline viewer
- Sources manager

**Not production Chrome extension** — the side-panel UI is a **simulator / preview**, not a published extension store package.

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)**.

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
