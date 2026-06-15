# Publish Link Analytics 4.2.0 to GitHub on one branch

## Repository

```text
https://github.com/sagarkerhalkar/link_studey
```

## Branch

```text
link-analytics-v4.2.0-project-source
```

## Automatic Windows command

Run from PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass

& "D:\LinkAnalytics\Link_Analytics_Shlink_Global_Port_2331\PUBLISH_TO_GITHUB_BRANCH.ps1"
```

The script:

1. verifies source version 4.2.0;
2. verifies the project and CI files;
3. clones the GitHub repository into a temporary directory;
4. creates one clean orphan branch;
5. copies the complete non-secret project source;
6. excludes `.env`, runtime databases, credentials, caches and raw private screen recordings;
7. commits and pushes the branch;
8. removes the temporary clone.

Git for Windows and GitHub authentication through Git Credential Manager are required. Never paste a GitHub token into the source files.

## GitHub integration status

The connected GitHub integration could read the repository but GitHub denied branch creation with HTTP 403 `Resource not accessible by integration`. This indicates that the installed GitHub App currently lacks the required repository-content/ref write permission. The local publishing script is included as a safe fallback.
