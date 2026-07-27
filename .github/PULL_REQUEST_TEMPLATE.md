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

Same commands as CI ([CONTRIBUTING](../CONTRIBUTING.md#checks-before-a-pr)):

- [ ] `make check` **or** `.\scripts\check.ps1` **or** the steps below
- [ ] Frontend: `npm run check` (`build` then `lint`)
- [ ] Backend: `uv run ruff check app tests` → `uv run alembic upgrade head` → `uv run pytest`
- [ ] Manual check (describe below if relevant)

## Checklist

- [ ] No secrets, `.env`, or personal keys (templates only)
- [ ] Public workflow changes reflected in README / CONTRIBUTING / `.env.example`
- [ ] Seed rows (if any) have honest prize / deadline / official URL fields
