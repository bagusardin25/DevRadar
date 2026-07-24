# DevRadar Backend API

Base path: `/api/v1`  
JSON field names: **camelCase**  
Errors: RFC 9457 `application/problem+json` with `traceId`

## Conventions

| Concern | Behavior |
|---|---|
| Collection body | `{ "items": [...], "nextCursor": "...\|null", "totalEstimate": N }` |
| Pagination | Cursor-based, `limit` 1–100 (default 20) |
| Default statuses | `verified_active`, `likely_active` |
| `needs_review` | Never returned by public catalogue or detail |
| Conditional GET | Detail routes send `ETag`; honor `If-None-Match` → `304` |
| Trace | Every response includes `X-Trace-Id` |

## Public catalogue

### `GET /hackathons`

Search and filter verified hackathons.

| Query | Type | Description |
|---|---|---|
| `q` | string | Full-text (`websearch_to_tsquery`) + trigram/title fallback |
| `mode` | `online` \| `hybrid` \| `in_person` | Participation mode |
| `region` | string | Matches `eligibleCountries`, `Worldwide`, or `location` |
| `eligibility` | string | Array membership (e.g. `Student`) |
| `technology` | string | Array membership (e.g. `Python`) |
| `status` | csv | Explicit statuses; `needs_review` is ignored |
| `deadlineBefore` / `deadlineAfter` | ISO datetime | Submission deadline range |
| `teamSize` | int ≥ 1 | Fits `teamMin`–`teamMax` |
| `prizeMin` | number | Minimum prize value |
| `onlyClosingSoon` | bool | Deadline within 14 days |
| `onlyBigPrizes` | bool | Prize ≥ 10000 |
| `cursor` | string | Opaque keyset cursor |
| `limit` | int | Page size (max 100) |

**Ordering:** `confidenceScore` DESC → submission deadline ASC → `id` ASC.

Example:

```http
GET /api/v1/hackathons?q=AI&mode=online&onlyClosingSoon=true&limit=20
```

```json
{
  "items": [
    {
      "id": "…-uuid-…",
      "slug": "global-ai-agents-2026",
      "title": "Global AI Agents Developer Challenge 2026",
      "organizer": "Anthropic & Vercel",
      "mode": "online",
      "verificationStatus": "verified_active",
      "confidenceScore": "0.980",
      "discoverySources": [],
      "audit": {
        "lastCheckedAt": "2026-07-23T21:45:00Z",
        "confidenceScore": "0.980",
        "scoreBreakdown": {
          "statusAndDeadline": 35,
          "keywordMatch": 25,
          "sourceCredibility": 20,
          "freshness": 14,
          "completeness": 4
        },
        "verifierNotes": "…",
        "checkedUrls": [],
        "pipelineStep": "verified"
      }
    }
  ],
  "nextCursor": "eyJzIjoiMC45OCIsInQiOiIuLi4iLCJpIjoiLi4uIn0=",
  "totalEstimate": 12
}
```

### `GET /hackathons/{slug}`

Detail with provenance (`discoverySources`) and `audit`.  
Headers: `ETag`, optional request `If-None-Match`.

### `GET /ai-offers`

| Query | Type | Description |
|---|---|---|
| `q` | string | Full-text / fuzzy |
| `offerType` | enum | e.g. `free_credits`, `free_tier` |
| `targetUser` | string | Array membership |
| `region` | string | Supported regions / Worldwide / Global |
| `status` | csv | Explicit public statuses |
| `expiresBefore` / `expiresAfter` | ISO datetime | Expiry window (`null` expiry = permanent) |
| `tags` | csv | All listed tags must match |
| `onlyFreeNoCard` | bool | `free_tier`, `free_credits`, `free_model`, `self_hosted_weights` |
| `cursor` / `limit` | | Same as hackathons |

**Ordering:** `confidenceScore` DESC → `expiresAt` ASC (nulls last) → `id` ASC.

### `GET /ai-offers/{slug}`

Detail with claim/terms URLs, provenance, and audit. Supports `ETag`.

### `GET /search`

Combined catalogue search with a kind discriminant.

| Query | Type | Description |
|---|---|---|
| `q` | string | Search text |
| `kind` | `hackathon` \| `ai_offer` | Optional kind filter |
| `status` | csv | Optional statuses |
| `cursor` / `limit` | | Pagination |

```json
{
  "items": [
    { "kind": "hackathon", "item": { "slug": "…", "title": "…" } },
    { "kind": "ai_offer", "item": { "slug": "…", "productName": "…" } }
  ],
  "nextCursor": null,
  "totalEstimate": 2
}
```

### `GET /stats`

Cached-friendly public counters for the dashboard.

```json
{
  "hackathonsActive": 12,
  "aiOffersActive": 8,
  "sourcesEnabled": 3,
  "lastIndexedAt": "2026-07-24T10:00:00Z"
}
```

### `GET /meta/filters`

Distinct filter values currently present in the public-facing tables (plus fixed mode/status lists).

```json
{
  "technologies": ["AI", "Python"],
  "regions": ["Worldwide", "Indonesia"],
  "eligibilityLabels": ["Student", "Developer"],
  "offerTypes": ["free_credits", "free_tier"],
  "modes": ["online", "hybrid", "in_person"],
  "verificationStatuses": ["verified_active", "likely_active"]
}
```

## Health (outside `/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | PostgreSQL + Redis readiness |

## Error example

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "hackathon not found",
  "instance": "http://localhost:8000/api/v1/hackathons/missing",
  "traceId": "…"
}
```
