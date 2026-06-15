# Build Verification — Link Analytics 4.2.0

## Automated results

- Pytest: **60 passed, 0 failed**
- Coverage: **88%**
- Ruff: **passed**
- Python compileall: **passed**
- Dependency integrity (`pip check`): **passed**

## Device calculation regressions

- Different browser-storage identities with the same physical-device signature merge into one estimated device.
- Two different hardware signatures on the same network remain separate devices.
- Existing 4.1 events without the new signature can merge using multiple matching hardware signals.
- Android desktop-site mode is classified as Android Mobile when touch/screen evidence supports it.
- Preview bots and incomplete requests do not change clicks, devices or repeats.

## Visual browser results

- Desktop: actual analytics template and CSS rendered in Chromium at 1600x1000.
- Mobile: actual analytics template and CSS rendered in Chromium at 390x844.
- Mobile horizontal overflow: **0px**.
- Screenshots are stored in `test-results/screenshots/`.

## Honest limitation

The build environment blocked Chromium network navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`. Server/live behavior is covered by Flask tests, and visual layout is covered by Chromium rendering through `page.set_content`. Physical platform/device acceptance must be completed after deployment.

## Deployment-path hotfix verification

- Python source compilation was rechecked after adding documentation and the Windows rebuild helper.
- No Python analytics code or database schema changed in this hotfix.
- The existing 4.2.0 validation artifacts remain included: 60 tests passed, 88% coverage, Ruff passed, dependency check passed, and desktop/mobile Chromium rendering passed.
- The PowerShell helper performs runtime validation of project files, `.env`, Docker Compose, build result, startup, health and readiness on Windows.
