# Current Release Status — Link Analytics 4.2.0

## Status

**READY FOR DEPLOYMENT AND REAL-DEVICE ACCEPTANCE TEST**

Automated logic, regression, coverage, static-analysis and responsive Chromium-render tests passed. Physical Android/iPhone/iPad and app-platform acceptance remains required.

## Resolved in code

- Browser/app identities no longer equal physical devices.
- Cross-context estimated-device grouping added.
- Existing 4.1 rows can be recalculated using hardware fallback.
- Preview bots and incomplete requests remain excluded.
- Global analytics UI redesigned for clarity.
- Live background refresh retained.

## Still pending

- Physical WhatsApp, Telegram, Instagram, Google Chat, Android Chrome, iPhone Safari and iPad Safari matrix.
- Confirmation that the user's real-device clicks group as expected after deploying 4.2.0.
- Broader macOS/Safari acceptance.

## Platform-identification status in 4.2.0

Version 4.2.0 retains the 4.1 platform-detection improvements. The 4.2 code change primarily corrects device estimation and redesigns analytics; it does not claim perfect identification when an app removes all source evidence.

Evidence already observed from the user's real diagnostic:

- Instagram was Confirmed from `com.instagram.android` and `l.instagram.com` evidence.
- WhatsApp preview traffic was identifiable.
- A following external-browser click can be labelled WhatsApp Probable only when conservative preview correlation matches; otherwise it remains Unknown / Hidden.
- Preview/bot requests are excluded from verified click and device totals.
