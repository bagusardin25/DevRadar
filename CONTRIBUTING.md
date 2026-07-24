# Contributing to DevRadar

Thanks for helping improve an open-source **hackathon + free AI offer** radar for developers.

This guide is for **first-time contributors** and regulars. Setup detail also lives in the root [README](README.md).

---

## Ways to contribute

| Kind | How |
|------|-----|
| **Bugs / ideas** | [GitHub Issues](https://github.com/bagusardin25/DevRadar/issues) (bug & feature templates) |
| **Code** | Backend (FastAPI), frontend (React/Vite), connectors, tests |
| **Catalogue data** | Edit seed JSON **or** use in-app **Submit** (preferred over mocks) |
| **Docs that ship** | README, this file, `SECURITY.md`, issue templates — **not** a private `docs/` folder |

**Good first PRs:** typo/UI copy fix, one honest seed listing, badge/layout polish, a failing test that documents a bug.

---

## Prerequisites

1. **Docker Desktop** running (Postgres on **5434**, Redis **6379**)
2. **[uv](https://docs.astral.sh/uv/)** + Python **3.12+**
3. **Node.js 20+** and npm

You do **not** need OpenAI, X/Twitter API, or GitHub OAuth to browse the seed catalogue.

---

## Repo map (orientation)

```
DevRadar/
├── src/                    # React frontend (Vite)
├── backend/app/            # FastAPI API, catalogue, ingestion, alerts
├── backend/scripts/        # seed, recheck, default sources
├── data/manual-collection/ # seed_listings.json  ← curated public data
├── infra/compose.yaml      # Postgres + Redis (+ MinIO)
└── scripts/dev.ps1|dev.sh  # one-shot bootstrap
```

Public app modules: **Radar** (hackathons), **AI Deals**.  
**Review / Pipeline / Sources** need an admin GitHub OAuth session (operators only).

---

## Development setup

### 1. Bootstrap (once)

**Windows (PowerShell):**

```powershell
git clone https://github.com/bagusardin25/DevRadar.git
cd DevRadar
.\scripts\dev.ps1
```

**macOS / Linux:**

```bash
git clone https://github.com/bagusardin25/DevRadar.git
cd DevRadar
chmod +x scripts/dev.sh
./scripts/dev.sh
# or: make bootstrap
```

This starts Docker services, creates `backend/.env` (from `.env.example`, secrets generated, `LLM_PROVIDER=disabled`), migrates, seeds the demo catalogue, and installs npm deps if needed.

### 2. Run API + UI (two terminals)

```powershell
# Terminal A — API
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal B — UI
npm run dev
```

| URL | Purpose |
|-----|---------|
| http://localhost:5173/ | App |
| http://127.0.0.1:8000/health/ready | API + Postgres + Redis |

If the UI shows **Backend Offline**, Docker or the API is not up.

Env knobs: `backend/.env.example` → copy is already made by bootstrap as `backend/.env` (never commit `.env`).

---

## Checks before a PR

```bash
# Backend
cd backend
uv run pytest -q
uv run ruff check app tests

# Frontend (repo root)
npm run build
npm run lint
```

CI runs the same class of checks on pull requests (frontend build/lint + backend pytest with services).

---

## Adding opportunities (data)

| Do | Don’t |
|----|--------|
| Prefer **official URLs** (rules, pricing, Devpost event page) | Use only a viral social post as the primary URL |
| Set honest `prize_label` when the pool is unknown (`TBA · …`) | Invent prize amounts |
| PR against `data/manual-collection/seed_listings.json` **or** use in-app **Submit** | Treat `src/data/mockData.ts` as the source of truth |
| Keep X posts as **provenance** (`x_posts`), not full post text | Store scraped X timelines long-term |

After editing seed JSON:

```bash
cd backend
uv run python scripts/seed_x_mcp_collection.py          # insert new slugs only
uv run python scripts/seed_x_mcp_collection.py --update # refresh existing fields
```

Optional: re-fetch official AI offer pages (rules; LLM if configured):

```bash
uv run python scripts/recheck_listings.py --kind ai_offer --limit 25
```

### Trust model (short)

- **Tier 1** — official site / docs  
- **Tier 2** — aggregators (Devpost, MLH, …)  
- **Tier 3** — social discovery (X, etc.) — lead only, not sole truth  

---

## Code guidelines

- **Backend:** Python 3.12+, type hints, async SQLAlchemy, Pydantic v2; JSON to the frontend is **camelCase**.
- **Frontend:** TypeScript; keep the public catalogue simple; keep admin tools behind auth.
- Prefer **small PRs** with a clear *why* (problem + approach).
- No secrets, API keys, or real `.env` contents in commits.

---

## Pull request checklist

- [ ] Problem and solution described  
- [ ] Tests and/or short manual verification notes  
- [ ] No secrets / `.env` / personal keys  
- [ ] If the **public** workflow changed: update **README** or this file  
- [ ] Seed rows (if any) have honest prize / deadline / official URL fields  

---

## Code of conduct

Be respectful. Harassment or spam of the review queue is not welcome. Maintainers may reject submissions or revoke abusive admin access.

## License

By contributing, you agree your contributions are licensed under the project’s [MIT License](LICENSE).
