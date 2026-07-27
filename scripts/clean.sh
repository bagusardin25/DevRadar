#!/usr/bin/env bash
# Remove local build, cache, and runtime artifacts. Never deletes backend/.env or seed JSON.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

rm -rf dist dist-ssr coverage .turbo .vite playwright-report test-results blob-report
rm -rf .ruff_cache .pytest_cache .mypy_cache .cache htmlcov
rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.cache
rm -rf backend/htmlcov backend/data
rm -f .coverage dump.rdb appendonly.aof celerybeat-schedule celerybeat-schedule.*
rm -f backend/.coverage backend/dump.rdb backend/celerybeat-schedule backend/celerybeat-schedule.*

find . \( -path './node_modules' -o -path './backend/.venv' -o -path './.git' \) -prune -o \
  \( -type d -name '__pycache__' -print \) 2>/dev/null |
  while IFS= read -r d; do rm -rf "$d"; done

find . \( -path './node_modules' -o -path './backend/.venv' -o -path './.git' \) -prune -o \
  \( -type f \( -name '*.py[cod]' -o -name '*.tsbuildinfo' -o -name '.coverage.*' -o -name 'celerybeat-schedule.*' \) -print \) 2>/dev/null |
  while IFS= read -r f; do rm -f "$f"; done

echo "Clean complete (backend/.env and seed data preserved)."
