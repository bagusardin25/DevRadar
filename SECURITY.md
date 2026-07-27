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

## Operator checklist

- Generate unique `SESSION_SECRET`, `EMAIL_ENCRYPTION_KEY`, `EMAIL_HMAC_KEY`  
- Never commit `.env`  
- Restrict `ADMIN_GOOGLE_EMAILS` to verified operator addresses only  

- Use HTTPS in production  
- Keep dependencies updated  

Thank you for helping keep DevRadar safe for self-hosters and users.
