# Manual collection dumps

- `candidates.example.jsonl` — schema sample (safe to commit).
- `candidates.jsonl` — real curated lead rows from X MCP.
- `seed_listings.json` — **deduplicated, enriched catalogue seed** derived from those X hits (official URLs + X provenance). Wave-2 (2026-07-25) added 15 online/virtual hackathons from a fresh X search.

## Seed into PostgreSQL

**Yes — open Docker Desktop first.** Backend needs Postgres (port **5434**) + Redis (**6379**) from `infra/compose.yaml`. API process itself runs on the host (`uvicorn`); only infra runs in Docker.

Easiest path from repo root:

```powershell
# Windows
.\scripts\dev.ps1

# Unix / make
./scripts/dev.sh
# or: make bootstrap
```

Manual steps:

```powershell
docker compose -f infra/compose.yaml up -d
cd backend
uv run alembic upgrade head
uv run python scripts/seed_listings.py --dry-run
uv run python scripts/seed_listings.py
```

Then start the API and frontend — catalogue shows seeded hackathons and AI offers.

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# other terminal
npm run dev
```

- Re-run seed **skips** existing slugs (`skip … (exists)`).
- Refresh prize labels / core fields: `uv run python scripts/seed_listings.py --update`
- Prefer editing **this seed file** for OSS data PRs, not `src/data/mockData.ts`.
