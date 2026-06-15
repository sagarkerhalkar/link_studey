# Windows Deployment — Version 4.0.0

The complete command-by-command procedure is in the root `README.md`. This file is a deployment checklist.

## Upgrade checklist

```powershell
cd "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
docker compose down
Copy-Item .env "D:\LinkAnalytics\LinkAnalytics.env.backup" -Force
cd "D:\LinkAnalytics"
Rename-Item "Link_Analytics_Shlink_Global_Port_2331" "Link_Analytics_Shlink_Global_Port_2331_backup_before_v4"
```

Extract the new ZIP into `D:\LinkAnalytics`, then:

```powershell
Copy-Item `
  "D:\LinkAnalytics\LinkAnalytics.env.backup" `
  "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\.env" `
  -Force

cd "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
Get-Content .\VERSION.txt
Set-ExecutionPolicy -Scope Process Bypass
.\start_windows.ps1 -Rebuild -SkipBrowser
```

Expected version: `4.0.0`.

## Local verification

```powershell
Invoke-RestMethod http://127.0.0.1:2331/healthz
Invoke-RestMethod http://127.0.0.1:2331/readyz
Invoke-RestMethod http://127.0.0.1:2332/rest/health
docker compose ps
```

## Cloudflare routes

```text
analytics.sagarkerhalkar.com -> http://localhost:2331
s.sagarkerhalkar.com         -> http://localhost:2331
```

## Public verification

```powershell
curl.exe -sS https://analytics.sagarkerhalkar.com/healthz
curl.exe -sS https://analytics.sagarkerhalkar.com/readyz
curl.exe -I https://analytics.sagarkerhalkar.com/login
```

Do not use `-ResetData` during upgrade.
