# Manual X discovery (MCP) — v0 data collection

For the first data waves we **do not** run the automated `x_recent_search` crawler on a schedule.  
Instead: search X via the **hosted X MCP** (`xapi`), curate official URLs by hand, then run DevRadar’s normal **fetch → parse → OpenAI extract → review** pipeline.

## Why manual first

| Automated crawler later | Manual MCP now |
|---|---|
| Needs stable query budget + rate limits | Pay-per-use only when you search |
| Stores discovery_signals at scale | Small curated list of real opportunities |
| Harder to tune noise | Human filters spam / retweets |

Search in the **product** (catalogue) still uses **PostgreSQL**. X MCP is only a **lead source**.

---

## 1. One-time: X app + Grok MCP

1. Create an app in the [X Developer Portal](https://developer.x.com/en/portal/dashboard).
2. Under User authentication settings, set **OAuth 2.0** and callback:
   - `http://localhost:8080/callback`
3. Copy **Client ID** and **Client Secret**.
4. Set Windows user environment variables (then **restart Grok TUI**):

```powershell
# PowerShell (current user, permanent)
[System.Environment]::SetEnvironmentVariable("X_CLIENT_ID", "YOUR_CLIENT_ID", "User")
[System.Environment]::SetEnvironmentVariable("X_CLIENT_SECRET", "YOUR_CLIENT_SECRET", "User")
```

Or paste real values into `~/.grok/config.toml` under `[mcp_servers.xapi.env]` (local only — never commit).

5. Grok config (already documented):

```toml
[mcp_servers.xapi]
command = "npx"
args = ["-y", "@xdevplatform/xurl", "mcp", "https://api.x.com/mcp"]
enabled = true
startup_timeout_sec = 300

[mcp_servers.xapi.env]
CLIENT_ID = "${X_CLIENT_ID}"
CLIENT_SECRET = "${X_CLIENT_SECRET}"
```

6. In Grok: `/mcps` → refresh (`r`) → enable **xapi**.  
   First connection opens a browser for OAuth. If tools fail with enrollment errors, move the app to **Pay-per-use / Production** in the X console.

Optional CLI (same credentials):

```powershell
npx -y @xdevplatform/xurl auth apps add devradar --client-id $env:X_CLIENT_ID --client-secret $env:X_CLIENT_SECRET
npx -y @xdevplatform/xurl auth oauth2 --app devradar
```

---

## 2. Search queries (examples)

Prefer **links + official accounts**; drop pure hype posts.

**Hackathons**

```
hackathon (register OR registration OR prize OR "apply now") has:links -is:retweet
("MLH" OR Devpost OR "hackathon") (deadline OR "last day" OR "closing soon") has:links -is:retweet
```

**AI free tiers / credits**

```
("free credits" OR "free tier" OR "developer credits" OR "$100" credits) (API OR AI OR LLM) has:links -is:retweet
("student pack" OR "startup credits" OR "open source program") (OpenAI OR Anthropic OR Google OR AWS OR Azure) has:links -is:retweet
```

Curated account filters (when useful): `from:MLHacks`, `from:devpost`, vendor official accounts.

---

## 3. What to save (curated row)

Append one JSON object per line to `data/manual-collection/candidates.jsonl`.

Schema:

```json
{
  "collected_at": "2026-07-24T12:00:00+00:00",
  "listing_kind": "hackathon",
  "source": "x_mcp",
  "post_url": "https://x.com/…/status/…",
  "post_id": "…",
  "author": "…",
  "official_url": "https://…",
  "notes": "short why it looks real",
  "status": "pending_fetch"
}
```

Rules:

- Prefer **official_url** (landing / rules / pricing), not only the post.
- Do **not** store full post text long-term if you want parity with Tier-3 privacy notes; `notes` can be short.
- `status`: `pending_fetch` → `fetched` → `in_review` → `published` / `rejected`.

Example file: `candidates.example.jsonl`.

---

## 4. After you have official URLs

1. **Fetch + extract** (API / Celery with OpenAI enabled), or community submit:
   - `POST /api/v1/submissions` with the official URL, or
   - admin enqueue `ingestion.fetch_document` with `listing_kind`.
2. **Admin review** approve → publish.
3. Update the JSONL row `status`.

No frontend wiring required for this path.

---

## 5. Later (not now)

- Enable scheduled `x_recent_search` connector + `X_BEARER_TOKEN` / OAuth app-only.
- Auto-create `discovery_signals` from connector hits.

Until then: **MCP search → human curate → pipeline**.
