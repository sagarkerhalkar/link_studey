# Project Issue Log — Link Analytics

This file is the permanent issue register for the project. New issues must be appended here and their status updated rather than removed.

## Status definitions

- `OPEN` — reproduced or reported and not yet accepted as fixed.
- `IN PROGRESS` — code or diagnostics are being worked on.
- `READY FOR REAL-DEVICE TEST` — automated validation passed, but physical-device acceptance is still required.
- `CLOSED` — verified with the required evidence.

## Issue register

| ID | Date | Severity | Status | Issue | Evidence / finding | Required acceptance |
|---|---|---:|---|---|---|---|
| LA-001 | 2026-06-15 | Critical | CLOSED | Initial Shlink PostgreSQL password mismatch | Existing Docker volume used an older password than the newly generated `.env`. | Fresh setup starts with matching DB credentials. |
| LA-002 | 2026-06-15 | High | CLOSED | First administrator password prompt was confusing in Docker/PowerShell | `getpass` could not control terminal echo; pasted values could be captured in the wrong order. | Admin can be created/reset with documented commands. |
| LA-003 | 2026-06-15 | Critical | CLOSED | Cloudflare Tunnel showed Error 1033 / Down | Old tunnel token returned `Unauthorized: Invalid tunnel secret`. | New token installed; connector becomes Healthy. |
| LA-004 | 2026-06-15 | Critical | CLOSED | Short domain routed directly to Shlink port 2332 | This bypassed the custom tracking gateway. | Both public hostnames route to port 2331; Shlink 2332 remains private. |
| LA-005 | 2026-06-15 | Critical | READY FOR REAL-DEVICE TEST | Android/mobile clicks can still appear as Linux Desktop | Real diagnostic includes enriched `Linux Desktop` rows with desktop Linux user-agent and no client payload. User reports these correspond to mobile activity. | A fresh physical Android click on a new tag must show Android Mobile / Android and never Linux Desktop. |
| LA-006 | 2026-06-15 | Critical | READY FOR REAL-DEVICE TEST | WhatsApp platform is not consistently confirmed from the same generic short link | Real diagnostic shows a WhatsApp preview user-agent as server-only/bot, while browser clicks can arrive as Unknown / Hidden when WhatsApp opens external Chrome and strips evidence. | Confirm WhatsApp only from actual evidence; otherwise show Hidden without false attribution. Preview requests must not contaminate human/device totals. |
| LA-007 | 2026-06-15 | Critical | READY FOR REAL-DEVICE TEST | Preview/bot requests can be confused with user clicks | Diagnostic contains `WhatsApp/2.23.20.0` and `facebookexternalhit` server-only bot rows. | Preview/bot requests must be isolated from human clicks, unique devices, repeat clicks and platform/device charts. |
| LA-008 | 2026-06-15 | High | CLOSED | Diagnostic command displayed null client fields | The diagnostic script incorrectly looked for `payload.client`; the database stores the client object directly. Correct diagnostic and regression tests added. | Correct raw client fields are read directly and used for device classification. |
| LA-009 | 2026-06-15 | Critical | OPEN | Physical-platform acceptance was previously claimed using simulated browser headers | Previous automated tests emulated Android and manually inserted `X-Requested-With`. | Do not claim physical WhatsApp/Instagram verification without real-device evidence. |
| LA-010 | 2026-06-15 | High | READY FOR REAL-DEVICE TEST | Instagram identification works when package/referrer evidence is present | Real diagnostic IDs 7, 10 and 11 show Android Mobile, Instagram, package `com.instagram.android`, and `l.instagram.com` referrer. | Repeat on clean tag and confirm correct per-device grouping and live updates. |
| LA-011 | 2026-06-15 | High | OPEN | Device-wise click grouping requires real-device acceptance | Requirement is one anonymous device row with total clicks and repeat count. | Same Android browser opens same short URL 3 times: 1 device, 3 clicks, 2 repeats. |
| LA-012 | 2026-06-15 | High | OPEN | Live analytics refresh requires physical deployment acceptance | Automated Chromium polling test exists, but user reports portal does not visibly update correctly. | Keep analytics page open; new click appears in background without full-page refresh or flicker. |
| LA-013 | 2026-06-15 | High | OPEN | Old/incorrect records can confuse current results | Earlier Shlink/v2/v3 data and prior tests can remain visible. | Current analytics view must clearly isolate current verified gateway events and separate legacy/test data. |
| LA-014 | 2026-06-15 | Medium | OPEN | Responsive compatibility requires broader real-device matrix | Automated 390×844 Chromium test is not equal to all physical Apple/Android devices and browsers. | Record acceptance on Android Chrome, iPhone Safari, iPad Safari, Windows Edge/Chrome, macOS Safari/Chrome and a tablet. |

## Latest real diagnostic summary — 2026-06-15

Source: `docs/project-resources/real-device-diagnostic-2026-06-15.txt`

Observed:

- Instagram events were correctly confirmed as Android Mobile / Android using package and referrer evidence.
- A WhatsApp preview request was detected as `server-only`, `is_bot=true`, browser/platform WhatsApp.
- Facebook preview requests were detected as `facebookexternalhit`, `server-only`, `is_bot=true`.
- Several rows marked `enriched` had null client payload fields and were stored as Linux Desktop or Windows PC.
- Therefore the enrichment state and human/device aggregation logic require correction before the release can be accepted.

## Rule

No issue may be marked `CLOSED` only because unit tests pass. A requirement involving a physical platform/device must include the required real-device acceptance evidence.

## 4.1.0 resolution activity — 2026-06-15

- Added verified-only aggregation.
- Added preview/bot and incomplete-request isolation.
- Added Linux desktop-site mobile heuristic.
- Added WhatsApp preview correlation with Probable confidence.
- Added 56-test regression suite and 88% coverage result.
- Physical acceptance remains required before closing LA-005, LA-006, LA-007, LA-011 and LA-012.

## 4.2.0 device-calculation and UI activity — 2026-06-15

| ID | Date | Severity | Status | Issue | Evidence / finding | Required acceptance |
|---|---|---:|---|---|---|---|
| LA-015 | 2026-06-15 | Critical | READY FOR REAL-DEVICE TEST | Device total overcounted browser/app contexts as physical devices | User CSV contains 9 verified clicks and 7 browser-storage IDs. Chrome and messaging-app WebViews can produce separate storage IDs on the same phone. | Same physical phone across Chrome and one or more app WebViews must remain one estimated device while browser/app identities remain visible separately. |
| LA-016 | 2026-06-15 | High | READY FOR REAL-DEVICE TEST | Analytics page was too technical and difficult for normal users | User screenshots show dense technical panels and explanations before actionable insights. | Global view must show verified clicks, estimated devices, repeats, platform quality, top platform/device/country and clear per-device cards before technical details. |
| LA-017 | 2026-06-15 | High | CLOSED IN AUTOMATION | Mobile layout and global view required fresh regression evidence | Prior screenshots were from earlier versions. | Actual 4.2 template/CSS rendered in Chromium at desktop and 390x844 with no horizontal overflow. Physical Safari/Android acceptance remains under LA-014. |

### 4.2 implementation status

- Browser/app identity and estimated-device identity are now separate metrics.
- Cross-context merge uses a privacy-safe signature plus salted network scope.
- Existing 4.1 rows can use a hardware-signal fallback without deleting data.
- Device cards show browser/app identity count so merges remain auditable.
- Automated acceptance is complete; real Android/iPhone/iPad acceptance is still required before closing LA-015 and LA-016.

## 4.2.0 deployment path correction — 2026-06-15

| ID | Date | Severity | Status | Issue | Evidence / finding | Resolution |
|---|---|---:|---|---|---|---|
| LA-018 | 2026-06-15 | Medium | CLOSED | Rebuild/start commands were executed from `D:\LinkAnalytics`, not the application directory | Docker returned `no configuration file provided: not found`; PowerShell could not find `start_windows.ps1`. | Added `REBUILD_AND_START_WINDOWS.ps1`, which resolves its own directory and can be called by absolute path from any PowerShell location. Added a deployment path hotfix document and corrected deployment instructions. |

## GitHub/source synchronization activity — 2026-06-15

| ID | Date | Severity | Status | Issue | Evidence / finding | Resolution |
|---|---|---:|---|---|---|---|
| LA-019 | 2026-06-15 | Medium | CLOSED | Running Docker image was 4.2.0 but the previously extracted Windows source did not contain `REBUILD_AND_START_WINDOWS.ps1` | Absolute-path execution returned `CommandNotFoundException`; the helper existed only in the later repackaged source. | Added the helper to the canonical 4.2.0 source, documented manual fallback commands, and prepared the full non-secret source for a dedicated GitHub branch. |

## GitHub integration permission — 2026-06-15

| ID | Date | Severity | Status | Issue | Evidence / finding | Resolution |
|---|---|---:|---|---|---|---|
| LA-020 | 2026-06-15 | Medium | OPEN EXTERNAL PERMISSION | Connected GitHub integration cannot create the requested branch | GitHub returned HTTP 403 `Resource not accessible by integration` while creating `link-analytics-v4.2.0-project-source`. Repository metadata is readable, but ref/content write permission is unavailable to the integration. | Grant the GitHub App repository Contents/Administration write permission, or run `PUBLISH_TO_GITHUB_BRANCH.ps1` locally through Git Credential Manager. |

