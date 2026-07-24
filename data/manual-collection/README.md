# Manual collection dumps

- `candidates.example.jsonl` — schema sample (safe to commit).
- `candidates.jsonl` — real curated lead rows from X MCP.
- `seed_listings.json` — **deduplicated, enriched catalogue seed** derived from those X hits (official URLs + X provenance).

See `docs/manual-x-collection.md`.

## Seed into PostgreSQL

From the repo, with Docker Postgres up and migrations applied:

```powershell
# infra
docker compose -f infra/compose.yaml up -d

# migrate
cd backend
uv run alembic upgrade head

# dry-run
uv run python scripts/seed_x_mcp_collection.py --dry-run

# insert (idempotent by slug)
uv run python scripts/seed_x_mcp_collection.py
```

Then start the API and open the frontend — catalogue should show the seeded hackathons and free AI offers.

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# other terminal
npm run dev
```

Re-running the seed script **skips** existing slugs (`skip … (exists)`).
