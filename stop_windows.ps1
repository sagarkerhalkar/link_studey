$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
docker compose down
Write-Host "Link Analytics services stopped." -ForegroundColor Green
