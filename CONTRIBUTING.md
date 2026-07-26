# Contributing to DevRadar

Thanks for helping improve an open-source **hackathon + free AI offer** radar for developers.

This guide is for **first-time contributors** and regulars. Setup detail also lives in the root [README](README.md).

---

## Ways to contribute

| Kind | How |
|------|-----|
| **Bugs / feature ideas** | [GitHub Issues](https://github.com/bagusardin25/DevRadar/issues) (bug & feature templates) |
| **Code** | Backend (FastAPI), frontend (React/Vite), connectors, tests |
| **Catalogue data** | Edit seed JSON **or** use in-app **Submit** (preferred over mocks) |
| **Docs that ship** | README, this file, `SECURITY.md`, issue templates — **not** a private `docs/` folder |
| **Security reports** | **Do not** open a public issue — follow [SECURITY.md](SECURITY.md) |
| **Usage questions** | Fine to open an issue as `question` — please keep the tracker actionable (one topic per thread) |

**Good first PRs:** typo/UI copy fix, one honest seed listing, badge/layout polish, a failing test that documents a bug.

---

## Prerequisites

1. **Docker Desktop** running (Postgres on **5434**, Redis **6379**)
2. **[uv](https://docs.astral.sh/uv/)** + Python **3.12+**
3. **Node.js 20+** and npm

You do **not** need OpenAI, X/Twitter API, or GitHub OAuth to browse the seed catalogue.

---

## Your first pull request

New to the project? This is the Git workflow. Setup commands are in **Development setup** below.

1. **Fork** the repo via the GitHub UI (top-right **Fork** button).
2. **Clone your fork** and add the upstream remote:

   ```bash
   git clone https://github.com/<your-username>/DevRadar.git
   cd DevRadar
   git remote add upstream https://github.com/bagusardin25/DevRadar.git
   ```

3. **Create a branch** off `main` with a type prefix — never commit directly to `main`:

   ```bash
   git checkout -b fix/short-description
   ```

   Prefixes: `feat/` (new capability), `fix/` (bug), `docs/` (docs-only), `refactor/`, `test/`, `chore/` (tooling / deps / build).

4. Run the bootstrap (see next section), make your change, and run the checks in **Checks before a PR**.
5. **Sync with upstream** before you push, to avoid conflicts:

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

6. **Push** to your fork and open a PR against `bagusardin25/DevRadar:main`:

   ```bash
   git push origin fix/short-description
   ```

   Then open the PR from GitHub (it will offer a "Compare & pull request" button).
7. Fill in the [PR checklist](#pull-request-checklist) at the bottom of this file.

**Big or ambiguous changes?** Open an issue first so we can align on scope before you invest time. Typo fixes, one seed listing, or a failing test can go straight to PR.

**Commit message style:** short imperative subject line ("Add X", "Fix Y", "Rename Z"). Check `git log` for examples.

**If CI fails:** click the failing check on your PR, fix the issue locally, then `git push` again — the PR updates automatically.

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

If you already cloned your fork in the previous section, skip the `git clone` line and just run the bootstrap script.

**Windows (PowerShell):**

```powershell
git clone https://github.com/<your-username>/DevRadar.git
cd DevRadar
.\scripts\dev.ps1
```

**macOS / Linux:**

```bash
git clone https://github.com/<your-username>/DevRadar.git
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

### 3. Background worker (optional)

Only needed for jobs that run outside a request: source scans (the hero's
**Scan sources** toggle), scheduled catalogue rechecks, and alert scans. Browsing
the catalogue works without it.

```powershell
# Terminal C — Celery worker
cd backend
uv run celery -A app.worker.celery_app worker -Q fetch -l info --pool=solo
```

`--pool=solo` is required on Windows (Celery's default `prefork` pool is
POSIX-only). Without a worker running, a live discovery run stays `queued` and
the UI will tell you so.

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

### CI gates (required to merge)

Every PR to `main` runs these on GitHub Actions (`.github/workflows/ci.yml`) — a green check is required to merge:

- **Frontend build** — `npm ci && npm run build` on Node 22
- **Frontend lint** — `npm run lint`
- **Backend tests** — `pytest` against a real Postgres 16 + Redis 7 (services spun up in CI), after `alembic upgrade head`

If a check goes red on your PR, click it → fix locally → `git push` again to re-run.

### The test database

`pytest` does **not** use your development database. It creates and migrates a
separate `devradar_test` database on first run, so your seeded catalogue is never
touched — some tests commit rows, and the migration round-trip test drops the
whole schema. Override the target with `TEST_DATABASE_URL` if needed.

If your catalogue ever does come back empty, re-seed it (both scripts are
idempotent):

```bash
cd backend
uv run python scripts/seed_x_mcp_collection.py   # demo catalogue
uv run python scripts/seed_default_sources.py    # aggregator sources
```

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

## How we review

Every PR gets two passes:

1. **Automated first-pass** from [CodeRabbit](https://coderabbit.ai) — posts a summary in the PR description and inline suggestions on the diff. Configured via [`.coderabbit.yaml`](.coderabbit.yaml). It's a **helper, not a merge gate** — treat suggestions as prompts to double-check, not blockers.
2. **Maintainer review** — a human always makes the final call on correctness, scope, and security. Aiming for a first response within a few days (best-effort — solo maintainer).

You can re-trigger the bot in a PR comment: `@coderabbitai review` (fresh review) or `@coderabbitai resolve` (mark all suggestions resolved).

---

## Code of conduct

Be respectful. Harassment or spam of the review queue is not welcome. Maintainers may reject submissions or revoke abusive admin access.

## License

By contributing, you agree your contributions are licensed under the project’s [MIT License](LICENSE).
