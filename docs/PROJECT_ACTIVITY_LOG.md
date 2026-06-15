# Project Activity Log — Link Analytics

This is the chronological project activity record. Every future diagnostic, code change, test run, deployment change and release package must be appended here.

## 2026-06-15

### Requirements consolidated

- Recorded the non-negotiable requirement for one unchanged short URL across all platforms.
- Recorded platform, device, per-device click count, total/repeat clicks, platform-wise analytics, link-wise analytics, live background refresh, responsive UI, CI/CD and detailed README requirements.

### Source review

- Reviewed the uploaded 2.0.x, 2.1.0, 3.0.0 and 4.0.0 packages.
- Identified dashboard port 2331, private Shlink port 2332, PostgreSQL storage and dashboard SQLite storage.

### Deployment diagnostics

- Diagnosed initial PostgreSQL authentication mismatch caused by an old Docker volume.
- Documented safe first-install reset and warned against production `-ResetData` use.
- Diagnosed administrator password prompt/terminal echo issue and documented secure password reset.
- Verified local dashboard health, readiness and Shlink health.
- Diagnosed Cloudflare Error 1033.
- Confirmed connector token failure with `Unauthorized: Invalid tunnel secret`.
- Documented token refresh/reinstall and Cloudflare route setup.
- Corrected public routing requirement so both `analytics.sagarkerhalkar.com` and `s.sagarkerhalkar.com` pass through port 2331.

### Tracking revisions

- Removed the separate platform-tagged-link design because it violated the single-link requirement.
- Added gateway/device/platform tracking attempts and live analytics polling.
- Added isolation for current gateway events from legacy Shlink/v2/v3 data.
- Added automated unit/integration/browser tests and screenshots.

### Real diagnostic received

- Stored the user's latest diagnostic export in `docs/project-resources/real-device-diagnostic-2026-06-15.txt`.
- Confirmed Instagram can be identified correctly when Android package/referrer evidence is present.
- Confirmed WhatsApp and Facebook preview requests occur and must be kept outside human/device analytics.
- Confirmed unresolved defect: some rows marked `enriched` contain no client payload and are classified as Linux Desktop/Windows PC.
- Marked physical WhatsApp/mobile acceptance as unresolved.

### Project-resource policy added

- Every new issue, diagnostic, test result, deployment activity and code change must be stored in this package.
- Every future source release must update the canonical current project-resource package rather than leaving the newest code only in chat attachments.
- Old release history remains in changelog/log files; the canonical current package always contains the latest complete source.

### Version 4.1.0 corrective implementation

- Reproduced the user's diagnostic sequence in automated regression tests.
- Corrected the diagnostic interpretation: client payload is stored directly, not nested.
- Changed primary analytics to count only enriched non-bot browser events.
- Excluded server-only requests and preview bots from device/platform totals.
- Added touch/screen/pixel-ratio override for Android browsers using Linux/X11 desktop-site mode.
- Added 120-second preview correlation for WhatsApp and other platform previews, labelled Probable.
- Added device confidence/evidence to UI and exports.
- Ran dependency, compile, Ruff, pytest and coverage validation: 56 passed, 88% coverage.
- Attempted fresh Playwright Chromium acceptance; environment blocked browser network access with ERR_BLOCKED_BY_ADMINISTRATOR.
- Prepared 4.1.0 source and deployment package; physical Android acceptance remains pending.

### User CSV and UI evidence reviewed

- Stored `chatgpt-gateway-v4.1-analytics.csv` in project resources.
- Measured 11 request rows, 9 verified clicks, 2 preview/bot requests and 7 browser-storage IDs.
- Confirmed the device-count defect: browser/app identities were being presented as physical devices.
- Reviewed the supplied screenshots and recorded the requirement for a simpler global, business-readable analytics view.

### Version 4.2.0 implementation

- Added a browser-generated device signature that excludes localStorage, cookie, browser name and full user-agent.
- Combined the signature with salted network and normalized OS scope to reduce accidental merging.
- Added a hardware-signal fallback for existing 4.1 events.
- Added separate `Estimated devices` and `Browser/app identities` metrics.
- Updated per-device aggregation to show all clicks, platforms and browser/app identity count under one estimated device.
- Redesigned analytics into an executive summary, request funnel, platform-quality donut, top insights, global charts, device cards and simplified evidence cards.
- Kept background polling at approximately 1.5 seconds without full-page refresh.
- Added three device-calculation regressions and one global-view regression.
- Ran 60 tests with 88% measured coverage; Ruff, compile and dependency checks passed.
- Rendered the actual template/CSS in Chromium at desktop and 390x844; mobile overflow measured 0px.
- Attempted networked Chromium acceptance; environment returned `ERR_BLOCKED_BY_ADMINISTRATOR`, recorded as blocked rather than passed.

### Version 4.2.0 deployment-path hotfix

- Recorded the failed deployment attempt caused by running Docker Compose from `D:\LinkAnalytics` rather than the application directory.
- Added `REBUILD_AND_START_WINDOWS.ps1` at the project root.
- The helper validates the source files and `.env`, changes to the correct directory automatically, validates Compose, builds the dashboard without cache, starts the application and checks health/readiness.
- Added `docs/DEPLOYMENT_PATH_HOTFIX_4_2.md` and updated the Windows deployment guide.
- No analytics logic or database schema was changed by this hotfix.

### GitHub branch publication and rebuild-helper synchronization

- Confirmed the canonical repository as `sagarkerhalkar/link_studey`.
- Added `REBUILD_AND_START_WINDOWS.ps1` to the current 4.2.0 project source so rebuild/start can be launched by absolute path from any PowerShell directory.
- Recorded the user report that Docker was already running 4.2.0 while the helper script was absent from the older extracted Windows source folder.
- Prepared the complete 4.2.0 source, documentation, tests, CI workflows and non-secret evidence for publication on a dedicated GitHub branch.
- `.env`, credentials, Cloudflare tunnel tokens and other secrets are intentionally excluded from GitHub.

### GitHub write-permission result and local publisher added

- Attempted to create branch `link-analytics-v4.2.0-project-source` in `sagarkerhalkar/link_studey` through the connected GitHub integration.
- GitHub returned HTTP 403: `Resource not accessible by integration`; no branch or commit was created.
- Added `PUBLISH_TO_GITHUB_BRANCH.ps1` as a safe Windows fallback using Git Credential Manager.
- Added `docs/GITHUB_PUBLISH_WINDOWS.md` with branch, exclusions, verification and publish steps.
- The publisher excludes `.env`, runtime databases, credentials, caches and raw private screen recordings.

