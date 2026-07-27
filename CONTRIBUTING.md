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

1. **Docker Desktop** (or Engine + Compose) — Postgres on host **5434**, Redis **6379**, optional MinIO **9000**
2. **[uv](https://docs.astral.sh/uv/)** + Python **3.12+**
3. **Node.js 20+** and npm (GitHub Actions uses **Node 22**)

You do **not** need OpenAI, X/Twitter API, or Google OAuth to browse the seed catalogue.

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
├── src/                         # React + Vite frontend
│   ├── api/                     # HTTP clients (camelCase *.ts)
│   ├── components/              # UI (PascalCase *.tsx; feature folders camelCase)
│   ├── hooks/ utils/ types/     # shared frontend modules
│   └── data/mockData.ts         # offline fallback only — not the seed source of truth
├── backend/
│   ├── app/                     # FastAPI packages (snake_case)
│   │   ├── api/public|admin/    # HTTP routes
│   │   ├── catalog/             # domain package name (US spelling)
│   │   ├── ingestion/ discovery/ submissions/ …
│   │   └── worker/              # Celery app
│   ├── scripts/                 # ops CLI (seed_*.py, recheck_*.py)
│   ├── tests/                   # mirrors app packages where practical
│   ├── alembic/versions/        # {revision}_{slug}.py
│   ├── .env.example             # development template → backend/.env
│   └── .env.production.example  # production checklist (not for local seed-demo)
├── data/manual-collection/      # curated seed_listings.json (+ candidates example)
├── infra/                       # Compose + Postgres init (local infra only)
├── scripts/                     # monorepo bootstrap / check / clean (.sh + .ps1)
├── public/                      # static assets served by Vite
└── .github/workflows/ci.yml     # secret scan, frontend, backend
```

### Naming conventions

| Area | Rule | Examples |
|------|------|----------|
| Python packages / modules | `snake_case` | `ai_review/`, `seed_listings.py` |
| Alembic revisions | `{hex}_{snake_slug}.py` | `a41d5b70c8ef_submission_review_lifecycle.py` |
| React components | `PascalCase.tsx` | `AdminQueue.tsx` |
| React non-UI modules | `camelCase.ts` | `formatPrize.ts`, `adminCatalogue.ts` |
| Feature subfolders (UI) | `camelCase/` | `components/adminCatalogue/` |
| Data / infra dirs | `kebab-case` | `manual-collection/`, `compose.yaml` |
| Root tooling scripts | short verb names | `dev`, `check`, `clean` (+ `.sh`/`.ps1`) |

**Spelling note:** the domain package is `app.catalog` (US). Product copy and some HTTP paths use **catalogue** (e.g. `/admin/catalogue`). Prefer consistency within a layer; do not rename the package without an intentional API migration.

Public app modules: **Radar** (hackathons), **AI Deals**.  
**Review / Catalog / Pipeline / Sources** need an admin Google OAuth session (operators only).
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

This starts Docker **infra** (Postgres / Redis / MinIO), creates `backend/.env` from
`backend/.env.example` (secrets generated; `LLM_PROVIDER=disabled`), migrates, seeds
the demo catalogue + default sources, and installs npm deps if needed.

### 2. Run API + UI + worker (three terminals)

Same flow as the [README quick start](README.md#quick-start-full-stack):

```powershell
# Terminal A — API
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal B — UI
npm run dev

# Terminal C — Celery fetch/review worker
cd backend
uv run celery -A app.worker.celery_app worker -Q fetch -l info --pool=solo
```

On Linux/macOS you can omit `--pool=solo`, or use `make api` / `make frontend` / `make worker`.

| URL | Purpose |
|-----|---------|
| http://localhost:5173/ | App |
| http://127.0.0.1:8000/health/ready | API + Postgres + Redis |

If the UI shows **Backend Offline**, Docker or the API is not up.

The worker is required for automatic community-submission fetching and AI review. It
also runs source scans (the hero's **Scan sources** toggle), scheduled catalogue
rechecks, and alert scans. Browsing the catalogue works without it, but submissions
remain `queued`.

Env: bootstrap already wrote `backend/.env` from `backend/.env.example` (never commit
`.env`). Optional frontend vars: root [`.env.example`](.env.example).

---

## Checks before a PR

Use the **same commands and order as CI**. Prefer the one-liners when possible.

### One command (recommended)

```bash
# Linux / macOS (infra must already be up — make bootstrap or make up)
make check

# Windows (PowerShell)
.\scripts\check.ps1
# or: npm run check:all
```

### Command matrix (single source of truth)

| Step | Local (raw) | Make | CI |
|------|-------------|------|-----|
| Install frontend | `npm ci` or `npm install` | — | `npm ci` |
| Frontend build | `npm run build` | `make build-frontend` | `npm run build` |
| Frontend lint | `npm run lint` | `make lint-frontend` | `npm run lint` |
| Frontend both | `npm run check` | `make check-frontend` | `npm run check` |
| Install backend | `cd backend && uv sync --all-extras` | — | `uv sync --all-extras --frozen` |
| Backend lint | `cd backend && uv run ruff check app tests` | `make lint-backend` | same |
| Migrate | `cd backend && uv run alembic upgrade head` | `make migrate` | same |
| Backend test | `cd backend && uv run pytest` | `make test-backend` | same |
| Backend all three | — | `make check-backend` | lint → migrate → pytest |
| Full gate | — | `make check` / `scripts/check.*` | frontend job + backend job |

Notes:

- **Pytest flags** (`-q --tb=short`) are set in `backend/pyproject.toml` (`addopts`) so every runner matches CI without repeating flags.
- **Install vs check:** local day-to-day can use `uv sync --all-extras` (allows lock updates). CI uses `--frozen` (`make sync-backend`) so the lockfile is authoritative.
- **Migrate** upgrades the DB used by the API; `pytest` still creates/uses a separate `devradar_test` database (see below). Running `alembic upgrade head` before tests matches CI and keeps your dev schema current.
- **Order matters for parity:** frontend = build then lint; backend = ruff → migrate → pytest.

### CI gates (required to merge)

Every PR to `main` runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | What it runs |
|-----|----------------|
| **Secret scan** | Gitleaks (full history) |
| **Frontend** | Node **22** (`.nvmrc`): `npm ci` → `npm run check` |
| **Backend** | Python **3.12**, Postgres **16** (:5434), Redis **7**: `uv sync --all-extras --frozen` → extensions → ruff → alembic → pytest |

CI env: `LLM_PROVIDER=disabled`, `OBJECT_STORAGE_BACKEND=memory`, same DB URL shape as `backend/.env.example`.

If a check goes red, fix locally with `make check` / `.\scripts\check.ps1`, then `git push` again.

### The test database

`pytest` does **not** use your development database. It creates and migrates a
separate `devradar_test` database on first run, so your seeded catalogue is never
touched — some tests commit rows, and the migration round-trip test drops the
whole schema. Override the target with `TEST_DATABASE_URL` if needed.

If your catalogue ever does come back empty, re-seed it (both scripts are
idempotent):

```bash
cd backend
uv run python scripts/seed_listings.py           # demo catalogue
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
uv run python scripts/seed_listings.py          # insert new slugs only
uv run python scripts/seed_listings.py --update # refresh existing fields
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
- No secrets, API keys, or real `.env` contents in commits. Templates only (`.env.example`). Local `backend/.env` and `candidates.jsonl` are gitignored — do not force-add them.


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

1. **Automated first-pass** from [CodeRabbit](https://coderabbit.ai) — summary + inline notes on the diff. Configured via [`.coderabbit.yaml`](.coderabbit.yaml) with profile **`quiet`** (security/correctness focus; skips lockfiles, seed JSON, and style already covered by ruff/oxlint/CI). **Helper, not a merge gate.**
2. **Maintainer review** — a human always makes the final call on correctness, scope, and security. Aiming for a first response within a few days (best-effort — solo maintainer).

Useful PR comments: `@coderabbitai review` (fresh review), `@coderabbitai resolve` (mark suggestions resolved). Skip auto-review with title keywords `wip` / `do not review` or label `skip-review`.

---

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Be respectful. Harassment or spam of the review queue is not welcome. Maintainers may reject submissions or revoke abusive admin access.

## License

By contributing, you agree your contributions are licensed under the project’s [MIT License](LICENSE).
