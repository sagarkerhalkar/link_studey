# Deploy Link Analytics 4.2.0 on Windows without deleting data

## Safety rules

Never run these during an upgrade:

```powershell
.\start_windows.ps1 -ResetData
docker compose down -v
```

They can remove users, links or analytics.

## Upgrade commands

## Recommended rebuild command from any PowerShell directory

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\REBUILD_AND_START_WINDOWS.ps1"
```

The helper changes to the correct project directory automatically, validates `.env` and Docker Compose, builds without cache, starts the application and checks health/readiness.


```powershell
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
docker compose down
Copy-Item ".env" "D:\LinkAnalytics\LinkAnalytics.env.backup" -Force
Set-Location "D:\LinkAnalytics"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Rename-Item "Link_Analytics_Shlink_Global_Port_2331" "Link_Analytics_Shlink_Global_Port_2331_backup_4_1_$Stamp"
$Zip = "$HOME\Downloads\Link_Analytics_Shlink_Global_4.2.0_Global_Device_Analytics.zip"
Expand-Archive -Path $Zip -DestinationPath "D:\LinkAnalytics" -Force
Copy-Item "D:\LinkAnalytics\LinkAnalytics.env.backup" "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\.env" -Force
Set-Location "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331"
Get-Content .\VERSION.txt
docker compose build --no-cache dashboard
.\start_windows.ps1 -SkipBrowser
```

The version must be `4.2.0` before and after the Docker rebuild:

```powershell
Get-Content .\VERSION.txt
docker compose exec dashboard sh -lc "cat /app/VERSION.txt"
```

## Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:2331/healthz
Invoke-RestMethod http://127.0.0.1:2331/readyz
Invoke-RestMethod http://127.0.0.1:2332/rest/health
```

## Public routing

Both domains route to the custom gateway:

```text
analytics.sagarkerhalkar.com -> http://localhost:2331
s.sagarkerhalkar.com         -> http://localhost:2331
```

## Public tests

```powershell
curl.exe -sS https://analytics.sagarkerhalkar.com/healthz
curl.exe -sS https://analytics.sagarkerhalkar.com/readyz
curl.exe -I --max-time 20 https://analytics.sagarkerhalkar.com/login
```
