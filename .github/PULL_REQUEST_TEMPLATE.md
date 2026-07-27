## Summary

<!-- What problem does this solve, and how? -->

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Docs / hygiene
- [ ] Refactor (no behaviour change)
- [ ] Tests only
- [ ] Chore (deps, CI, tooling)

## How tested

Mirrors CI / CONTRIBUTING checks:

- [ ] `cd backend && uv run ruff check app tests`
- [ ] `cd backend && uv run pytest -q`
- [ ] `npm run build` and `npm run lint`
- [ ] Manual check (describe below if relevant)

## Checklist

- [ ] No secrets, `.env`, or personal keys (templates only)
- [ ] Public workflow changes reflected in README / CONTRIBUTING / `.env.example`
- [ ] Seed rows (if any) have honest prize / deadline / official URL fields
