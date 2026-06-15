[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$ComposeFile = Join-Path $ProjectRoot "docker-compose.yml"
$StartScript = Join-Path $ProjectRoot "start_windows.ps1"
$VersionFile = Join-Path $ProjectRoot "VERSION.txt"
$EnvFile = Join-Path $ProjectRoot ".env"

Write-Host "============================================================"
Write-Host " LINK ANALYTICS | SAFE REBUILD AND START"
Write-Host "============================================================"
Write-Host "Project root: $ProjectRoot"

if (-not (Test-Path $ComposeFile)) {
    throw "docker-compose.yml was not found in $ProjectRoot"
}

if (-not (Test-Path $StartScript)) {
    throw "start_windows.ps1 was not found in $ProjectRoot"
}

if (-not (Test-Path $VersionFile)) {
    throw "VERSION.txt was not found in $ProjectRoot"
}

if (-not (Test-Path $EnvFile)) {
    throw ".env was not found in $ProjectRoot. Restore the saved .env before rebuilding."
}

$Version = (Get-Content $VersionFile -Raw).Trim()
Write-Host "Source version: $Version"

Set-Location $ProjectRoot

Write-Host "Validating Docker Compose configuration..."
docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host "Building the dashboard image without cache..."
docker compose build --no-cache dashboard
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard image build failed."
}

Write-Host "Starting Link Analytics..."
& $StartScript -SkipBrowser
if ($LASTEXITCODE -ne 0) {
    throw "Link Analytics startup failed."
}

Write-Host "Waiting for the dashboard..."
Start-Sleep -Seconds 5

$Health = Invoke-RestMethod "http://127.0.0.1:2331/healthz"
$Ready = Invoke-RestMethod "http://127.0.0.1:2331/readyz"

Write-Host "Health status: $($Health.status)"
Write-Host "Readiness status: $($Ready.status)"
Write-Host "Dashboard: http://127.0.0.1:2331"
Write-Host "Completed successfully."
