param(
    [switch]$Rebuild,
    [switch]$SkipBrowser,
    [switch]$DockerCheckOnly,
    [switch]$ResetData
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function New-RandomSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    } finally {
        $rng.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Get-EnvValue([string]$Name, [string]$DefaultValue) {
    if (Test-Path .env) {
        $match = Get-Content .env | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
        if ($match) {
            return ($match -split "=", 2)[1].Trim()
        }
    }
    return $DefaultValue
}

function Test-LocalPortAvailable([int]$Port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

function Invoke-DockerCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$Quiet,
        [switch]$AllowFailure
    )

    # Windows PowerShell 5.1 can convert a native program's stderr output into
    # PowerShell error records. Docker sometimes writes harmless warnings to
    # stderr even when its exit code is 0. Temporarily use Continue and decide
    # success only from Docker's native exit code.
    $previousPreference = $ErrorActionPreference
    $output = @()
    $exitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& docker @Arguments 2>&1)
        $exitCode = [int]$LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if (-not $Quiet) {
        foreach ($line in $output) {
            Write-Host "$line"
        }
    }

    $result = New-Object PSObject -Property @{
        ExitCode = $exitCode
        Output   = $output
    }

    if (($exitCode -ne 0) -and (-not $AllowFailure)) {
        $details = ($output | Out-String).Trim()
        throw "Docker command failed: docker $($Arguments -join ' ') (exit code $exitCode).`n$details"
    }

    return $result
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " LINK ANALYTICS | GATEWAY 2331 | SHLINK PRIVATE 2332" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is not installed or docker is not available in PATH. Install Docker Desktop, start it, and run this script again."
}

$dockerInfo = Invoke-DockerCommand -Arguments @("info") -Quiet -AllowFailure
if ($dockerInfo.ExitCode -ne 0) {
    $dockerDetails = ($dockerInfo.Output | Out-String).Trim()
    throw "Docker Desktop is installed but not ready. Start Docker Desktop and run this script again.`n$dockerDetails"
}
Write-Host "Docker Desktop is ready." -ForegroundColor Green

# Used by CI to execute the exact Docker-warning startup check without
# launching containers or changing the user's environment.
if ($DockerCheckOnly) {
    Write-Host "Docker warning compatibility check passed." -ForegroundColor Green
    exit 0
}

if ($ResetData) {
    Write-Host "Resetting only Link Analytics containers and data volumes..." -ForegroundColor Yellow
    $null = Invoke-DockerCommand -Arguments @("compose", "down", "-v", "--remove-orphans") -AllowFailure
    if (Test-Path .env) {
        Remove-Item .env -Force
    }
    Write-Host "Link Analytics local data was reset. Other Docker projects were not changed." -ForegroundColor Green
}

if (-not (Test-Path .env)) {
    $apiKey = New-RandomSecret 32
    $dbPassword = New-RandomSecret 24
    $secretKey = New-RandomSecret 48
    @"
SHLINK_DOMAIN=s.sagarkerhalkar.com
SHLINK_HOST_PORT=2332
SHLINK_API_KEY=$apiKey
POSTGRES_PASSWORD=$dbPassword
SECRET_KEY=$secretKey
GEOLITE_LICENSE_KEY=
SESSION_COOKIE_SECURE=0
"@ | Set-Content -Encoding UTF8 .env
    Write-Host "Created secure local .env configuration." -ForegroundColor Green
}

$shlinkHostPortText = Get-EnvValue -Name "SHLINK_HOST_PORT" -DefaultValue "2332"
$shlinkHostPort = 0
if (-not [int]::TryParse($shlinkHostPortText, [ref]$shlinkHostPort)) {
    throw "SHLINK_HOST_PORT in .env must be a valid number. Current value: $shlinkHostPortText"
}

# A failed previous startup may leave only the database running. Remove the
# stopped/failed Shlink container before checking the host port.
$null = Invoke-DockerCommand -Arguments @("compose", "rm", "-sf", "shlink") -Quiet -AllowFailure

if (-not (Test-LocalPortAvailable -Port $shlinkHostPort)) {
    throw "Port $shlinkHostPort is already in use. This build keeps the public dashboard/tracking gateway on port 2331 and uses port $shlinkHostPort only for the private Shlink API. Change SHLINK_HOST_PORT in .env to a free port such as 2333, then run again."
}
Write-Host "Shlink host port $shlinkHostPort is available." -ForegroundColor Green

if ($Rebuild) {
    $null = Invoke-DockerCommand -Arguments @("compose", "build", "--no-cache", "dashboard")
} else {
    $null = Invoke-DockerCommand -Arguments @("compose", "build", "dashboard")
}

$null = Invoke-DockerCommand -Arguments @("compose", "up", "-d", "shlink-db", "shlink")

Write-Host "Checking Shlink..." -ForegroundColor Yellow
$shlinkReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$shlinkHostPort/rest/health" -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $shlinkReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $shlinkReady) {
    $logResult = Invoke-DockerCommand -Arguments @("compose", "logs", "--tail", "120", "shlink") -Quiet -AllowFailure
    foreach ($line in $logResult.Output) { Write-Host "$line" }
    $logText = ($logResult.Output | Out-String)
    if ($logText -match "password authentication failed|database.*authentication|could not connect to.*database") {
        throw "Shlink could not authenticate to PostgreSQL. This usually means an old Docker volume has a different password. Because first setup has not completed, run: .\start_windows.ps1 -ResetData"
    }
    throw "Shlink did not become healthy. Review the detailed log above. For a clean first-install reset, run: .\start_windows.ps1 -ResetData"
}
Write-Host "Shlink is ready." -ForegroundColor Green

$null = Invoke-DockerCommand -Arguments @("compose", "run", "--rm", "dashboard", "flask", "--app", "run.py", "init-db")

$adminCheck = Invoke-DockerCommand -Arguments @("compose", "run", "--rm", "dashboard", "flask", "--app", "run.py", "has-admin") -Quiet -AllowFailure
if ($adminCheck.ExitCode -ne 0) {
    Write-Host "Create the first dashboard administrator." -ForegroundColor Cyan
    $adminUsername = (Read-Host "Username").Trim().ToLowerInvariant()
    $adminDisplayName = (Read-Host "Display name [Administrator]").Trim()
    if ([string]::IsNullOrWhiteSpace($adminDisplayName)) { $adminDisplayName = "Administrator" }

    $passwordOne = Read-Host "Password (minimum 12 characters)" -AsSecureString
    $passwordTwo = Read-Host "Repeat password" -AsSecureString
    $ptrOne = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($passwordOne)
    $ptrTwo = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($passwordTwo)
    try {
        $plainOne = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptrOne)
        $plainTwo = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptrTwo)
        if ($plainOne.Length -lt 12) { throw "Password must contain at least 12 characters." }
        if ($plainOne -cne $plainTwo) { throw "Passwords do not match." }

        $env:LA_ADMIN_USERNAME = $adminUsername
        $env:LA_ADMIN_DISPLAY_NAME = $adminDisplayName
        $env:LA_ADMIN_PASSWORD = $plainOne
        $null = Invoke-DockerCommand -Arguments @(
            "compose", "run", "--rm",
            "-e", "LA_ADMIN_USERNAME",
            "-e", "LA_ADMIN_DISPLAY_NAME",
            "-e", "LA_ADMIN_PASSWORD",
            "dashboard", "flask", "--app", "run.py", "create-admin-env"
        )
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptrOne)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptrTwo)
        Remove-Item Env:LA_ADMIN_USERNAME -ErrorAction SilentlyContinue
        Remove-Item Env:LA_ADMIN_DISPLAY_NAME -ErrorAction SilentlyContinue
        Remove-Item Env:LA_ADMIN_PASSWORD -ErrorAction SilentlyContinue
        Remove-Variable plainOne, plainTwo, passwordOne, passwordTwo -ErrorAction SilentlyContinue
    }
}

$null = Invoke-DockerCommand -Arguments @("compose", "up", "-d", "dashboard")

Write-Host "Checking dashboard..." -ForegroundColor Yellow
$dashboardReady = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:2331/healthz" -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $dashboardReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $dashboardReady) {
    $null = Invoke-DockerCommand -Arguments @("compose", "logs", "--tail", "80", "dashboard") -AllowFailure
    throw "Dashboard did not become healthy. Review the log above."
}

Write-Host ""
Write-Host "Dashboard: http://localhost:2331" -ForegroundColor Green
Write-Host "Shlink engine: http://localhost:$shlinkHostPort (private local service)" -ForegroundColor DarkGray
Write-Host "Short-domain target: s.sagarkerhalkar.com -> http://localhost:2331" -ForegroundColor Cyan
Write-Host "Dashboard target: analytics.sagarkerhalkar.com -> http://localhost:2331" -ForegroundColor Cyan

if (-not $SkipBrowser) {
    Start-Process "http://localhost:2331/login"
}
