# Source onboarding

## Adding a curated source

1. Prefer a **reviewed** Tier 1/2 definition (official site, Devpost, MLH, HackerEarth, RSS).
2. Create via admin API `POST /api/v1/admin/sources` — **never** put API secrets in the body.
3. Reference credentials only by environment key name (`credentialRef`, e.g. `X_BEARER_TOKEN`).
4. Attach one or more `source_queries` with module (`hackathon` / `ai_offer`), schedule interval, and `resultCap`.
5. Enable the source; the scheduler leases due queries and creates `crawl_runs`.

## Connector types

| Type | Role |
|---|---|
| `devpost` | Hackathon directory |
| `mlh` | MLH events |
| `hackerearth` | Challenges |
| `rss` | Generic RSS/Atom |
| `official_site` | Seed URL list for official pages |
| `x_recent_search` | Tier 3 discovery (Task 11) — automated crawler (later) |

### Manual X leads (preferred first)

Until the scheduled X crawler is enabled, discover leads with the **X MCP** (`xapi` in Grok) and curate rows under `data/manual-collection/`.  
Full steps: [`docs/manual-x-collection.md`](./manual-x-collection.md).

## Offline testing

Connectors accept fixtures so CI never hits live sites. Record redacted HTML/JSON under `tests/fixtures/`.
