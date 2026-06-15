param(
    [string]$RepositoryUrl = "https://github.com/sagarkerhalkar/link_studey.git",
    [string]$BranchName = "link-analytics-v4.2.0-project-source",
    [string]$CommitMessage = "Add Link Analytics 4.2.0 complete project source"
)

$ErrorActionPreference = "Stop"

$ProjectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExpectedVersion = "4.2.0"
$VersionFile = Join-Path $ProjectPath "VERSION.txt"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available in PATH. Install Git for Windows first."
}

if (-not (Test-Path $VersionFile)) {
    throw "VERSION.txt was not found in $ProjectPath"
}

$Version = (Get-Content $VersionFile -Raw).Trim()
if ($Version -ne $ExpectedVersion) {
    throw "Wrong source version. Expected $ExpectedVersion but found $Version."
}

$RequiredFiles = @(
    "README.md",
    "docker-compose.yml",
    "start_windows.ps1",
    "REBUILD_AND_START_WINDOWS.ps1",
    "link_analytics",
    "tests",
    ".github"
)

foreach ($RequiredFile in $RequiredFiles) {
    if (-not (Test-Path (Join-Path $ProjectPath $RequiredFile))) {
        throw "Required project item is missing: $RequiredFile"
    }
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("link-analytics-github-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null

try {
    Write-Host "Cloning repository..."
    git clone $RepositoryUrl $TempRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Git clone failed. Confirm repository access and GitHub authentication."
    }

    Push-Location $TempRoot
    try {
        $ExistingBranch = git ls-remote --heads origin $BranchName
        if ($ExistingBranch) {
            throw "Remote branch '$BranchName' already exists. Choose another branch name or delete the old branch intentionally."
        }

        git checkout --orphan $BranchName
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create orphan branch $BranchName"
        }

        git rm -rf . 2>$null | Out-Null

        Write-Host "Copying complete non-secret project source..."
        $ExcludedDirectories = @(
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".venv",
            "venv",
            "instance"
        )
        $ExcludedFiles = @(
            ".env",
            "*.db",
            "*.sqlite",
            "*.sqlite3",
            "*.pyc",
            "reported-screen-recording.mp4"
        )

        $RoboArgs = @(
            $ProjectPath,
            $TempRoot,
            "/E",
            "/COPY:DAT",
            "/R:2",
            "/W:1",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS",
            "/NP",
            "/XD"
        ) + $ExcludedDirectories + @("/XF") + $ExcludedFiles

        & robocopy @RoboArgs | Out-Null
        $RoboCode = $LASTEXITCODE
        if ($RoboCode -ge 8) {
            throw "Robocopy failed with exit code $RoboCode"
        }

        if (Test-Path ".env") {
            throw "Safety check failed: .env must never be committed."
        }

        git add --all
        if ($LASTEXITCODE -ne 0) {
            throw "git add failed"
        }

        $Pending = git status --porcelain
        if (-not $Pending) {
            throw "No files were staged for commit."
        }

        git commit -m $CommitMessage
        if ($LASTEXITCODE -ne 0) {
            throw "git commit failed. Configure Git user.name and user.email if requested."
        }

        git push -u origin $BranchName
        if ($LASTEXITCODE -ne 0) {
            throw "git push failed. Sign in through Git Credential Manager and ensure repository write access."
        }

        Write-Host ""
        Write-Host "Published successfully."
        Write-Host "Branch: $BranchName"
        Write-Host "Repository: $RepositoryUrl"
    }
    finally {
        Pop-Location
    }
}
finally {
    if (Test-Path $TempRoot) {
        Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
