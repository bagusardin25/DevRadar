# Mirror GitHub Actions CI gates (frontend + backend).
# Prerequisites: Docker infra up (Postgres :5434, Redis :6379), backend deps installed.
# Usage (repo root):  .\scripts\check.ps1   or   npm run check:all

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step([string]$Message) {
  Write-Host "`n==> $Message" -ForegroundColor Cyan
}

# --- Frontend (same as ci.yml frontend job after npm ci) ---
Step "Frontend build (npm run build)"
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Step "Frontend lint (npm run lint)"
npm run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --- Backend (same as ci.yml backend job after uv sync) ---
Push-Location (Join-Path $Root "backend")
try {
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
    exit 1
  }

  Step "Backend lint (uv run ruff check app tests)"
  uv run ruff check app tests
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  Step "Backend migrate (uv run alembic upgrade head)"
  uv run alembic upgrade head
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  Step "Backend test (uv run pytest)"
  uv run pytest
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
  Pop-Location
}

Write-Host "`nAll CI-parity checks passed." -ForegroundColor Green
