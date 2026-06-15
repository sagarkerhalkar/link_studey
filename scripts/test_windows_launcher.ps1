$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $projectRoot "start_windows.ps1"

# Parse the real launcher first.
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_.Message }
    throw "PowerShell parser found errors in start_windows.ps1"
}

$content = Get-Content $scriptPath -Raw
$required = @(
    "Invoke-DockerCommand",
    "DockerCheckOnly",
    "SHLINK_HOST_PORT",
    'DefaultValue "2332"',
    'http://127.0.0.1:$shlinkHostPort/rest/health',
    "http://127.0.0.1:2331/healthz",
    "create-admin"
)
foreach ($item in $required) {
    if (-not $content.Contains($item)) {
        throw "Launcher is missing required behavior: $item"
    }
}

# Execute the launcher with a fake docker.cmd which reproduces the user's
# exact condition: a warning is written to stderr, but Docker exits with 0.
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("link-analytics-docker-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null
$fakeDocker = Join-Path $tempDir "docker.cmd"
@'
@echo off
>&2 echo WARNING: DOCKER_INSECURE_NO_IPTABLES_RAW is set
if not "%FAKE_DOCKER_EXIT%"=="" exit /b %FAKE_DOCKER_EXIT%
exit /b 0
'@ | Set-Content -Encoding ASCII $fakeDocker

$oldPath = $env:PATH
$oldFakeExit = $env:FAKE_DOCKER_EXIT
$powerShellExe = (Get-Process -Id $PID).Path
try {
    $env:PATH = "$tempDir;$oldPath"
    Remove-Item Env:FAKE_DOCKER_EXIT -ErrorAction SilentlyContinue

    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File $scriptPath -DockerCheckOnly
    if ($LASTEXITCODE -ne 0) {
        throw "Launcher incorrectly failed when Docker emitted a warning and returned exit code 0."
    }

    # Also ensure a genuine Docker failure is not ignored.
    $env:FAKE_DOCKER_EXIT = "1"
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File $scriptPath -DockerCheckOnly *> $null
        $failureExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($failureExitCode -eq 0) {
        throw "Launcher incorrectly accepted a genuine Docker failure."
    }
} finally {
    $env:PATH = $oldPath
    if ($null -eq $oldFakeExit) {
        Remove-Item Env:FAKE_DOCKER_EXIT -ErrorAction SilentlyContinue
    } else {
        $env:FAKE_DOCKER_EXIT = $oldFakeExit
    }
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}

Write-Host "Windows launcher syntax, Docker warning handling, and real failure detection passed."
