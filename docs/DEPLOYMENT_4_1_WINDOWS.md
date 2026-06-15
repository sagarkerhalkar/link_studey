# Deploy Link Analytics 4.1.0 on Windows without deleting data

Do not use `-ResetData` and do not run `docker compose down -v`.

## 1. Stop existing containers

```powershell
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
docker compose down
```

## 2. Back up configuration

```powershell
Copy-Item ".env" "D:\LinkAnalytics\LinkAnalytics.env.backup" -Force
Test-Path "D:\LinkAnalytics\LinkAnalytics.env.backup"
```

Expected: `True`.

## 3. Rename old source folder

```powershell
Set-Location "D:\LinkAnalytics"
Rename-Item "Link_Analytics_Shlink_Global_Port_2331" "Link_Analytics_Shlink_Global_Port_2331_backup_before_4_1"
```

## 4. Extract the 4.1.0 ZIP into `D:\LinkAnalytics`

After extraction this must exist:

```powershell
Test-Path "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\start_windows.ps1"
```

Expected: `True`.

## 5. Restore `.env`

```powershell
Copy-Item "D:\LinkAnalytics\LinkAnalytics.env.backup" "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\.env" -Force
```

## 6. Rebuild and start

```powershell
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
Get-Content .\VERSION.txt
Set-ExecutionPolicy -Scope Process Bypass
.\start_windows.ps1 -Rebuild -SkipBrowser
```

Expected version: `4.1.0`.

## 7. Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:2331/healthz
Invoke-RestMethod http://127.0.0.1:2331/readyz
Invoke-RestMethod http://127.0.0.1:2332/rest/health
```

## 8. Cloudflare routes

Both public hostnames must point to port 2331:

```text
analytics.sagarkerhalkar.com -> http://localhost:2331
s.sagarkerhalkar.com         -> http://localhost:2331
```

Port 2332 stays private.

## 9. Clean acceptance test

Create a brand-new tag, share the same unchanged short URL through WhatsApp, open it twice from one Android phone, and keep analytics open. Expected: 2 verified clicks, 1 unique device, 1 repeat click, Android Mobile, and WhatsApp Confirmed/Strong or Probable depending on evidence.
