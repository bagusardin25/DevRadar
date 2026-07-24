# Contributing to DevRadar

Thanks for helping improve an open-source opportunity radar for developers.

## Ways to contribute

1. **Bug reports & feature ideas** — use GitHub Issues (templates under `.github/ISSUE_TEMPLATE/`).
2. **Code** — backend (FastAPI), frontend (React/Vite), connectors, docs.
3. **Catalogue data** — curated seed listings or in-app Submit (preferred over hardcoding mocks).
4. **Docs** — self-hosting, env setup, runbooks.

## Development setup

Follow the root **README** or:

```bash
# Unix
./scripts/dev.sh
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# other terminal
npm run dev
```

```powershell
# Windows
.\scripts\dev.ps1
```

Full stack steps are in the root **README** (bootstrap scripts + env example).

### Checks before PR

```bash
# Backend
cd backend
uv run pytest -q
uv run ruff check app tests

# Frontend
npm run build
npm run lint
```

CI runs backend tests (with services) and frontend build on pull requests.

## Adding opportunities (data)

| Do | Don’t |
|----|--------|
| Prefer **official URLs** (rules, pricing, Devpost event page) | Use only a viral social post as the primary URL |
| Set honest `prize_label` when the numeric pool is unknown (`TBA · …`) | Invent prize amounts |
| PR against `data/manual-collection/seed_listings.json` or use in-app **Submit** | Edit `src/data/mockData.ts` as the source of truth |
| Keep X posts as **provenance** (`x_posts`), not full post text long-term | Store full scraped X timelines |

After seed JSON changes:

```bash
cd backend
uv run python scripts/seed_x_mcp_collection.py          # new slugs
uv run python scripts/seed_x_mcp_collection.py --update # refresh fields
```

## Code guidelines

- **Backend:** Python 3.12+, type hints, async SQLAlchemy, Pydantic v2. CamelCase JSON to the frontend.
- **Frontend:** TypeScript, keep public catalogue UX simple; admin tooling behind auth.
- **Trust model:** X / social = Tier 3 discovery; official sites = Tier 1. See `konsep.md` / product docs.
- Prefer small, focused PRs with a clear description of *why*.

## Pull request checklist

- [ ] Describes the problem and solution  
- [ ] Tests or manual verification notes  
- [ ] No secrets, `.env`, or personal API keys  
- [ ] Docs updated if behavior/env changes  
- [ ] Seed data includes honest prize/deadline fields when applicable  

## Code of conduct

Be respectful. Harassment or bad-faith spam of the review queue is not welcome. Maintainers may reject submissions or ban abusive admin access.

## License

By contributing, you agree your contributions are licensed under the project’s [MIT License](LICENSE).
