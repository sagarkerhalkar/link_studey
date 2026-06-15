# Changelog

## 4.2.0 — 2026-06-15

### Device calculation correction

- Replaced the old assumption that one browser-storage ID equals one physical device.
- Added a second, privacy-safe estimated-device identity across Chrome, app WebViews and other browser contexts.
- The cross-context estimate uses a browser-generated hardware/screen signature combined with a salted network scope.
- Added a fallback for existing 4.1 records using OS, model, screen, pixel ratio, touch, hardware, timezone and language signals.
- Added separate metrics for estimated devices and browser/app identities.
- Per-device cards now show clicks, browser/app identity count, platforms, OS and estimate confidence.

### Analytics UI redesign

- Replaced the dense technical dashboard with a global executive view.
- Added request-to-audience funnel, platform-identification donut, top platform/device/country snapshot and simplified audience cards.
- Added app-versus-web, device, OS, browser and country cards.
- Replaced the dense recent-event table with readable evidence cards.
- Moved technical methodology and historical separation into an expandable details panel.
- Retained 1.5-second background refresh without a full-page reload.

### Validation

- Added cross-context device merge, non-merge and 4.1 hardware-fallback regression tests.
- 60 tests passed with 88% measured coverage.
- Ruff, compile and dependency checks passed.
- Actual template/CSS rendered in Chromium at 1600x1000 and 390x844; mobile horizontal overflow was 0px.
- Chromium network navigation in this build environment remained blocked by `ERR_BLOCKED_BY_ADMINISTRATOR`; it is not marked passed.
- Physical Android, iPhone, iPad and platform acceptance remains required.

## 4.1.0 — 2026-06-15

- Added verified-only aggregation, preview isolation, Android desktop-site detection and probable platform correlation.

## 4.2.0 documentation/deployment hotfix

- Added `REBUILD_AND_START_WINDOWS.ps1` so rebuild/start can be launched by absolute path from any PowerShell directory.
- Added explicit detection for missing `.env`, compose file, start script and version file.
- Added post-start health and readiness checks.
- Recorded deployment issue LA-018 in permanent project resources.
