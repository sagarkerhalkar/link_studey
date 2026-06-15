# Solution — Device calculation and global analytics UI (4.2.0)

## Evidence from the supplied CSV

The supplied `chatgpt-gateway-v4.1-analytics.csv` contains:

- 11 total request rows;
- 9 verified browser clicks;
- 2 preview/bot requests;
- 7 distinct browser-storage device IDs;
- 7 Android clicks and 2 Windows clicks.

The 7 IDs are browser/app identities, not proof of 7 physical devices. One phone can create separate localStorage spaces in Chrome, Telegram, WhatsApp and Instagram.

## Corrected model

Version 4.2 keeps two separate concepts:

1. **Browser/app identity** — stable inside one browser profile or WebView.
2. **Estimated device** — cross-context estimate built from a browser-generated hardware/screen signature and salted network scope.

The estimate excludes localStorage ID, cookie ID, browser name and full user-agent so these do not split one phone into several devices.

The application refuses to merge when there are not enough matching signals.

## UI correction

The page now starts with business-level answers:

- verified clicks;
- estimated devices;
- repeats;
- platform identification rate;
- browser/app identities;
- hidden-source clicks.

It then shows a request funnel, platform quality, top platform/device/country, platform mix, app-vs-web mix, device audience cards and a readable evidence trail.
