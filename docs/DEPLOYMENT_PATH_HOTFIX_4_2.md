# Deployment path hotfix — 4.2.0

## Reported problem

The commands were run from `D:\LinkAnalytics` instead of the application directory. Docker therefore returned:

```text
no configuration file provided: not found
```

PowerShell also returned:

```text
.\start_windows.ps1 is not recognized
```

## Cause

`docker-compose.yml` and `start_windows.ps1` are stored in:

```text
D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331
```

Docker Compose searches the current directory unless a compose file is supplied explicitly.

## Immediate correction

```powershell
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
Get-Content .\VERSION.txt
Test-Path .\.env
docker compose config --quiet
docker compose build --no-cache dashboard
.\start_windows.ps1 -SkipBrowser
```

The source version must show `4.2.0` and `.env` must return `True` before the build starts.

## Safer command that works from any directory

Run the helper by absolute path:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\REBUILD_AND_START_WINDOWS.ps1"
```

The helper resolves its own source directory, validates `.env`, validates Docker Compose, builds without cache, starts the application and checks health/readiness.

## Data safety

Do not run either of these during an upgrade:

```powershell
.\start_windows.ps1 -ResetData
docker compose down -v
```
