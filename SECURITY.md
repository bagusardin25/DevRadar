# Security Policy

## Supported versions

Security fixes are applied on a best-effort basis to the default branch of this repository.

## Reporting a vulnerability

**Do not** open a public GitHub issue for security problems that could enable:

- Auth bypass on admin routes  
- Remote code execution  
- Data exfiltration of subscriber emails or secrets  
- SSRF / abuse of the fetch pipeline against internal networks  

Instead, contact the maintainers privately (e.g. GitHub Security Advisory on the repository, or the email listed on the maintainer’s GitHub profile).

Please include:

- Description and impact  
- Steps to reproduce  
- Affected commit/version if known  

We will try to acknowledge reports within a reasonable time and coordinate disclosure after a fix is available.

## Scope notes

- End-user bookmarks live in **browser localStorage** — not a server secret store.  
- Alert emails are encrypted at rest when configured; default dev email provider is **console**.  
- The fetch pipeline implements SSRF protections; treat misconfiguration of `DATABASE_URL` / network as operator risk.  
- Community URL submission must remain rate-limited and validated.

## Secrets & local data hygiene

**Never commit** real environment files or keys. The repo only tracks templates:

| Safe to commit | Keep local / gitignored |
|----------------|-------------------------|
| `.env.example`, `backend/.env.example` | `backend/.env`, any `*.env` |
| `data/manual-collection/candidates.example.jsonl` | `data/manual-collection/candidates.jsonl` |
| Public seed `seed_listings.json` | Private keys (`*.pem`), cloud `credentials.json`, service-account JSON |

Sensitive values typically live only in `backend/.env` (created by bootstrap or copied from the example):

- `SESSION_SECRET`, `EMAIL_ENCRYPTION_KEY`, `EMAIL_HMAC_KEY`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
- `LLM_API_KEY` / `OPENAI_API_KEY`
- `X_BEARER_TOKEN`
- `RESEND_API_KEY`, `SMTP_PASSWORD`, `WEBHOOK_SECRET`
- Object-storage access keys when not using local MinIO defaults

**If a secret is committed or pasted into a public channel:** revoke/rotate it at the provider immediately, then rewrite or purge history if it reached a remote. Treat chat logs the same as accidental commits.

CI runs [Gitleaks](https://github.com/gitleaks/gitleaks) on every PR (`.gitleaks.toml`). Enable GitHub **secret scanning** + **push protection** on the repository settings for defense in depth.

## Docker build context & deployment

### Build context

Always build the API with the **backend** directory as context so the monorepo
frontend, git history, and local agent dirs never enter the daemon:

```bash
docker build -f backend/Dockerfile -t devradar-api:local backend
```

`backend/.dockerignore` excludes `.env*`, keys, `tests/`, caches, and `data/`.
Do **not** `COPY` env files in the Dockerfile — pass them only at **run** time:

```bash
docker run --rm -p 127.0.0.1:8000:8000 --env-file /secure/path/prod.env devradar-api:local
```

The image runs as a non-root user (`app`, uid 10001), uses a multi-stage build
(no `uv` binary in the final stage), and defaults `APP_ENV=production`.

### Local Compose (`infra/compose.yaml`)

- **Dev infra only** (Postgres / Redis / optional MinIO profile).
- Ports bind to **`127.0.0.1`** so services are not reachable on the LAN.
- Credentials are well-known demo values — **never** reuse for production.
- MinIO is behind Compose profile `object-storage` (not started by default).

### Production deploy (operator)

- Use managed Postgres/Redis (or hardened VMs), not the local Compose file.
- Inject env from a secret manager using `backend/.env.production.example` as a checklist.
- Put TLS termination in front of the API; set `TRUSTED_PROXY_HOPS` correctly.
- Publish container port 8000 only on a private network or via the reverse proxy.
- Run migrations as a one-shot job: `alembic upgrade head` before new traffic.
- Run Celery workers as separate processes/services with the same env (no secrets in image).

## Development vs production configuration

| | Development (`APP_ENV=development`) | Production (`APP_ENV=production`) |
|--|-------------------------------------|-----------------------------------|
| Template | [`backend/.env.example`](backend/.env.example) → `backend/.env` | [`backend/.env.production.example`](backend/.env.production.example) (checklist only) |
| Secrets | Placeholders OK for seed-demo; bootstrap generates local ones | Unique secrets required; placeholders **rejected at startup** |
| Database | Compose defaults (`devradar:devradar@…:5434`) | Strong credentials; Compose defaults **rejected** |
| Cookies | `Secure=false` (HTTP localhost) | `Secure=true` (HTTPS) |
| OpenAPI `/docs` | Enabled | Disabled |
| OAuth callback | Optional (`localhost` fallback) | `OAUTH_REDIRECT_BASE_URL` **https** required |
| Object storage | `local` filesystem OK | `memory` forbidden; `s3` needs real keys |

CI uses `APP_ENV=test` (same relaxed defaults as development for fixtures).

## Operator checklist

- Generate unique `SESSION_SECRET`, `EMAIL_ENCRYPTION_KEY`, `EMAIL_HMAC_KEY`  
- Never commit `.env` or paste live keys into issues/PRs  
- Restrict `ADMIN_GOOGLE_EMAILS` to verified operator addresses only  
- Set `APP_ENV=production` only on real hosts; use the production env checklist  
- Use HTTPS in production (`FRONTEND_URL`, `OAUTH_REDIRECT_BASE_URL`)  
- Keep dependencies updated  
- Prefer seed demo mode (`LLM_PROVIDER=disabled`) until you intentionally add keys  

Thank you for helping keep DevRadar safe for self-hosters and users.
