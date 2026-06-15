# Tracking Truth — Version 4.2.0

## Platform detection

One unchanged short URL is used. A platform is shown only from package headers, in-app signatures, referrers or conservative preview correlation. If the launching application removes all evidence, the result remains `Unknown / Hidden`.

## Device calculation

Browsers cannot expose a MAC address, IMEI or hardware serial number. Version 4.2 reports an **estimated device**, not a guaranteed physical identity.

The estimate uses:

- salted network scope;
- normalized operating system;
- screen dimensions and pixel ratio;
- touch capability;
- hardware concurrency and device memory when available;
- model, timezone, language and architecture when available.

Browser/app identities remain visible separately. This makes it possible to show that Chrome and an app WebView were merged into one estimated device.

## Excluded requests

Preview bots and incomplete collectors are excluded from verified clicks, device totals and repeat clicks.

## What changed between 4.1 and 4.2

- 4.1 improved platform evidence handling, preview correlation, bot isolation and Android desktop-site classification.
- 4.2 retains those changes and focuses on estimated-device grouping plus a simpler global analytics view.
- 4.2 does not create separate platform links and does not add source query parameters.
