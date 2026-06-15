# Test Results — Link Analytics 4.2.0

## Automated suite

- 60 passed
- 0 failed
- 88% measured coverage
- Python 3.13

## Static and dependency checks

- Ruff: passed
- compileall: passed
- pip check: no broken requirements

## Device calculation tests

- Same physical signature across two browser/app storage identities -> one estimated device.
- Different signatures on same network -> two devices.
- Existing 4.1 records without new signature -> hardware fallback merge.
- Android desktop-site Linux/X11 UA + mobile touch/screen -> Android Mobile.
- Preview bots/incomplete requests -> excluded.

## Visual tests

- Actual template/CSS rendered in Chromium at 1600x1000.
- Actual template/CSS rendered in Chromium at 390x844.
- Mobile horizontal overflow: 0px.

## Blocked test

Network navigation from Chromium to the local test server was blocked by the environment with `ERR_BLOCKED_BY_ADMINISTRATOR`. This is stored in `test-results/browser-network-acceptance-4.2.0.txt` and is not claimed as passed.
