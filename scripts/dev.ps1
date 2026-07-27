# DevRadar local bootstrap (Windows PowerShell)
# Usage (from repo root):
#   .\scripts\dev.ps1              # infra + migrate + seed
#   .\scripts\dev.ps1 -SkipSeed    # infra + migrate only
#   .\scripts\dev.ps1 -Api         # also start uvicorn (blocks)
#   .\scripts\dev.ps1 -Frontend    # also start Vite (blocks; run after API in another terminal)

param(
  [switch]$SkipSeed,
  [switch]$Api,
  [switch]$Frontend,
  [switch]$Help
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

if ($Help) {
  Write-Host @"
DevRadar local bootstrap

  .\scripts\dev.ps1              Start Docker infra, ensure backend/.env, migrate, seed demo data
  .\scripts\dev.ps1 -SkipSeed    Same without catalogue seed
  .\scripts\dev.ps1 -Api         After bootstrap, run API on :8000 (blocking)
  .\scripts\dev.ps1 -Frontend    After bootstrap, run Vite on :5173 (blocking)

Typical two-terminal flow after first bootstrap:
  Terminal A:  cd backend; uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  Terminal B:  npm run dev
"@
  exit 0
}

Write-Step "Checking Docker"
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker engine is not running. Start Docker Desktop, then re-run this script." -ForegroundColor Red
  exit 1
}

Write-Step "Starting Postgres + Redis + MinIO (infra/compose.yaml)"
docker compose -f infra/compose.yaml up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "Waiting for Postgres health"
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
  $status = docker compose -f infra/compose.yaml ps --format json 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue
  # Fallback: pg_isready
  docker compose -f infra/compose.yaml exec -T postgres pg_isready -U devradar 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) {
  Write-Host "Postgres did not become ready in time." -ForegroundColor Red
  exit 1
}

$envFile = Join-Path $Root "backend\.env"
$envExample = Join-Path $Root "backend\.env.example"
if (-not (Test-Path $envFile)) {
  Write-Step "Creating backend/.env from .env.example"
  Copy-Item $envExample $envFile
  # Generate simple secrets for local dev (not for production)
  $bytes = 1..48 | ForEach-Object { Get-Random -Maximum 256 }
  $secret = [Convert]::ToBase64String([byte[]]$bytes)
  $bytes2 = 1..48 | ForEach-Object { Get-Random -Maximum 256 }
  $secret2 = [Convert]::ToBase64String([byte[]]$bytes2)
  $bytes3 = 1..48 | ForEach-Object { Get-Random -Maximum 256 }
  $secret3 = [Convert]::ToBase64String([byte[]]$bytes3)
  $content = Get-Content $envFile -Raw
  $content = $content -replace 'SESSION_SECRET=.*', "SESSION_SECRET=$secret"
  $content = $content -replace 'EMAIL_ENCRYPTION_KEY=.*', "EMAIL_ENCRYPTION_KEY=$secret2"
  $content = $content -replace 'EMAIL_HMAC_KEY=.*', "EMAIL_HMAC_KEY=$secret3"
  # Seed-only demo: no LLM required
  $content = $content -replace 'LLM_PROVIDER=openai', 'LLM_PROVIDER=disabled'
  Set-Content -Path $envFile -Value $content -NoNewline
  Write-Host "  Wrote local secrets; LLM_PROVIDER=disabled (seed demo works without OpenAI)." -ForegroundColor Green
}

Write-Step "Installing backend deps (uv)"
Push-Location (Join-Path $Root "backend")
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
  exit 1
}
uv sync --all-extras
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }

Write-Step "Running migrations"
uv run alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }

if (-not $SkipSeed) {
  Write-Step "Seeding demo catalogue (idempotent by slug)"
  uv run python scripts/seed_x_mcp_collection.py
  if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
  Write-Step "Seeding default aggregator sources (Devpost/MLH/HackerEarth)"
  uv run python scripts/seed_default_sources.py
  if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
}
Pop-Location

if (-not (Test-Path (Join-Path $Root "node_modules"))) {
  Write-Step "Installing frontend deps (npm)"
  npm install
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "`nBootstrap complete." -ForegroundColor Green
Write-Host @"

Next:
  API:      cd backend; uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  Frontend: npm run dev
  Worker:   cd backend; uv run celery -A app.worker.celery_app worker -Q fetch -l info --pool=solo
  Health:   http://127.0.0.1:8000/health/ready
  App:      http://localhost:5173/

Demo data: data/manual-collection/seed_listings.json
Refresh prizes/labels: cd backend; uv run python scripts/seed_x_mcp_collection.py --update
"@

if ($Api) {
  Write-Step "Starting API on :8000"
  Push-Location (Join-Path $Root "backend")
  uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  Pop-Location
}

if ($Frontend) {
  Write-Step "Starting Vite on :5173"
  npm run dev
}
