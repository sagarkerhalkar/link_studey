# Link Analytics 4.2.0 — Global Device and Platform Analytics

Link Analytics is a self-hosted branded short-link analytics application. Version 4.2.0 keeps one unchanged short URL and corrects the device-counting model.

## What was wrong in 4.1

The 4.1 export contained 9 verified clicks but 7 browser-storage IDs. The application treated those 7 IDs as 7 devices even though the same phone can open a link through Chrome, Telegram WebView, WhatsApp WebView and Instagram WebView. Browser storage identifies a browser context, not necessarily a physical device.

## What 4.2 changes

- Displays **Estimated devices** separately from **Browser/app identities**.
- Merges browser contexts only when several privacy-safe signals agree.
- Shows each estimated device with total clicks, platforms, browser/app identity count, OS and confidence.
- Keeps previews, bots and incomplete collectors outside click/device totals.
- Provides a simplified global analytics view with a request funnel, platform quality, top platform/device/country and readable device cards.
- Updates silently in the background approximately every 1.5 seconds.

## Technical honesty

A browser cannot expose a MAC address, IMEI or hardware serial number. Device totals are privacy-safe estimates. Platform detection is evidence based; hidden sources remain `Unknown / Hidden` rather than being guessed.

## Architecture

```text
analytics.sagarkerhalkar.com -> Flask dashboard/gateway on port 2331
s.sagarkerhalkar.com         -> Flask tracking gateway on port 2331
Shlink REST/redirect engine  -> private localhost port 2332
PostgreSQL                   -> Shlink data
SQLite                       -> users, ownership and gateway analytics
```

Both public hostnames must route to port 2331. Port 2332 must remain private.

## Windows upgrade from 4.1 without deleting data

Do not run `-ResetData`. Do not run `docker compose down -v`.

### 1. Stop the current application

```powershell
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
docker compose down
```

### 2. Back up `.env`

```powershell
Copy-Item ".env" "D:\LinkAnalytics\LinkAnalytics.env.backup" -Force
Test-Path "D:\LinkAnalytics\LinkAnalytics.env.backup"
```

The result must be `True`.

### 3. Move outside the project folder

```powershell
Set-Location "D:\LinkAnalytics"
```

Close editors or Explorer windows that lock the source directory.

### 4. Rename the old source

```powershell
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Rename-Item `
  "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331" `
  "Link_Analytics_Shlink_Global_Port_2331_backup_4_1_$Stamp"
```

### 5. Extract 4.2.0

```powershell
$Zip = "$HOME\Downloads\Link_Analytics_Shlink_Global_4.2.0_Global_Device_Analytics.zip"
Expand-Archive -Path $Zip -DestinationPath "D:\LinkAnalytics" -Force
```

Verify:

```powershell
Test-Path "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\start_windows.ps1"
Get-Content "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\VERSION.txt"
```

Expected:

```text
True
4.2.0
```

### 6. Restore `.env`

```powershell
Copy-Item `
  "D:\LinkAnalytics\LinkAnalytics.env.backup" `
  "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\.env" `
  -Force
```

### 7. Rebuild without old cache

```powershell
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
Set-ExecutionPolicy -Scope Process Bypass
docker compose build --no-cache dashboard
.\start_windows.ps1 -SkipBrowser
```

### 8. Confirm source and container versions

```powershell
Get-Content .\VERSION.txt
docker compose exec dashboard sh -lc "cat /app/VERSION.txt"
```

Both must show `4.2.0`.

### 9. Health tests

```powershell
Invoke-RestMethod http://127.0.0.1:2331/healthz
Invoke-RestMethod http://127.0.0.1:2331/readyz
Invoke-RestMethod http://127.0.0.1:2332/rest/health
```

### 10. Cloudflare routes

```text
analytics.sagarkerhalkar.com -> http://localhost:2331
s.sagarkerhalkar.com         -> http://localhost:2331
```

Restart the connector from Administrator PowerShell:

```powershell
Restart-Service Cloudflared
Start-Sleep -Seconds 20
Get-Service Cloudflared
```

## Physical acceptance test

Create a new tag such as `device-v42-test`.

1. Keep its analytics page open.
2. Open the short URL twice in Android Chrome.
3. Open the same URL once from a messaging app WebView on the same phone.
4. Do not refresh the dashboard manually.

Expected:

```text
Verified clicks: 3
Estimated devices: 1
Browser/app identities: 2 (or more depending on app isolation)
Repeat clicks: 2
Device: Android Mobile
Linux Desktop: 0
```

If hardware evidence is missing, the application deliberately keeps browser identities separate rather than falsely merging people.

## Verification included in this package

- 60 automated tests passed.
- 88% measured code coverage.
- Ruff passed.
- Python compilation passed.
- Dependency integrity passed.
- Chromium desktop layout render passed.
- Chromium 390x844 mobile render passed with 0px horizontal overflow.
- Physical device acceptance is still required after deployment.

See `BUILD_VERIFICATION.md`, `TESTING_AND_CI.md`, `docs/PROJECT_ISSUE_LOG.md` and `docs/PROJECT_ACTIVITY_LOG.md`.

## Safe rebuild from any PowerShell directory

After extracting 4.2.0 and restoring `.env`, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\REBUILD_AND_START_WINDOWS.ps1"
```

This avoids the `no configuration file provided` and `start_windows.ps1 is not recognized` errors caused by running commands from `D:\LinkAnalytics` instead of the application directory.

## GitHub source branch

The complete non-secret 4.2.0 project source is maintained on the dedicated branch:

```text
link-analytics-v4.2.0-project-source
```

The branch includes `REBUILD_AND_START_WINDOWS.ps1`, tests, CI workflows, deployment documentation, issue/activity logs and test evidence. Runtime `.env` files, passwords, API keys and Cloudflare tunnel tokens are never committed.

### Publish the complete source to GitHub from Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass

& "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\PUBLISH_TO_GITHUB_BRANCH.ps1"
```

This publishes the non-secret 4.2.0 project to branch `link-analytics-v4.2.0-project-source` in `sagarkerhalkar/link_studey`. See `docs/GITHUB_PUBLISH_WINDOWS.md`.

