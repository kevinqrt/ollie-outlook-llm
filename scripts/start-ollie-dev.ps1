$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

Write-Host "Building frontend bundle..." -ForegroundColor Cyan
Push-Location $frontendDir
npm.cmd run build
Pop-Location

Write-Host "Launching Ollie Desktop Host..." -ForegroundColor Cyan
Push-Location $backendDir
$env:UV_CACHE_DIR = Join-Path $backendDir ".uv-cache"
if (-not (Test-Path $env:UV_CACHE_DIR)) {
    New-Item -ItemType Directory -Force $env:UV_CACHE_DIR | Out-Null
}
uv run --no-sync python -m app.desktop_host
Pop-Location
