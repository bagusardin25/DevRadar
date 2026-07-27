# Remove local build, cache, and runtime artifacts. Never deletes backend/.env or seed JSON.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$dirs = @(
  "dist", "dist-ssr", "coverage", ".turbo", ".vite",
  "playwright-report", "test-results", "blob-report",
  ".ruff_cache", ".pytest_cache", ".mypy_cache", ".cache", "htmlcov",
  "backend\.pytest_cache", "backend\.mypy_cache", "backend\.ruff_cache",
  "backend\.cache", "backend\htmlcov", "backend\data"
)

foreach ($d in $dirs) {
  $path = Join-Path $root $d
  if (Test-Path $path) {
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "removed $d"
  }
}

$files = @(
  ".coverage", "dump.rdb", "appendonly.aof", "celerybeat-schedule",
  "backend\.coverage", "backend\dump.rdb", "backend\celerybeat-schedule"
)
foreach ($f in $files) {
  $path = Join-Path $root $f
  if (Test-Path $path) {
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    Write-Host "removed $f"
  }
}

Get-ChildItem -Path $root -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object {
    $_.FullName -notmatch '\\node_modules\\|\\\.venv\\|\\\.git\\' -and (
      ($_.PSIsContainer -and $_.Name -eq '__pycache__') -or
      (-not $_.PSIsContainer -and (
        $_.Name -match '\.py[cod]$|\.tsbuildinfo$|^\.coverage\.' -or
        $_.Name -like 'celerybeat-schedule.*'
      ))
    )
  } |
  ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
  }

Write-Host "Clean complete (backend/.env and seed data preserved)."
