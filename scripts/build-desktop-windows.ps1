$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$backendDir = Join-Path $repoRoot "backend"
$distDir = Join-Path $backendDir "dist"

Write-Host "Building frontend bundle..." -ForegroundColor Cyan
Push-Location $frontendDir
npm.cmd run build
Pop-Location

Write-Host "Building Windows executable with PyInstaller..." -ForegroundColor Cyan
Push-Location $backendDir
$env:UV_CACHE_DIR = Join-Path $backendDir ".uv-cache"
if (-not (Test-Path $env:UV_CACHE_DIR)) {
    New-Item -ItemType Directory -Force $env:UV_CACHE_DIR | Out-Null
}
uv run --no-sync pyinstaller --noconfirm ollie_desktop.spec
Pop-Location

Write-Host "Build complete. Executable output:" -ForegroundColor Green
Write-Host (Join-Path $distDir "OllieDesktopHost.exe")
