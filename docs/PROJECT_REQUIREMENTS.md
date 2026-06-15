# Project Requirements — Link Analytics

This file consolidates the user's primary requirements into a single implementation contract.

## Non-negotiable behavior

1. One unchanged short URL must be shared on every platform.
2. No separate WhatsApp, Instagram, Telegram, Google Chat or other platform URLs.
3. The system must use all technically available evidence to identify the platform.
4. It must never invent a platform when the launching application hides its identity.
5. Android must never be shown as Linux.
6. Each anonymous device must appear with its total click count.
7. Total clicks, unique devices and repeat clicks must be visible.
8. Platform-wise and link-wise analytics must be available.
9. Analytics must update in the background without a visible page reload.
10. The interface must work on Android, iPhone, iPad, tablets, Windows, macOS and major browsers.
11. Every release must include debugging, automated tests, CI/CD and deployment instructions.
12. README documentation must explain every important command and expected result.

## Technical truth accepted by version 4

A browser cannot expose a physical MAC address. A single generic URL cannot guarantee WhatsApp/Instagram identification when the launching app opens external Chrome/Safari and strips all referrer/package/user-agent evidence.

In that case the correct platform result is `Unknown / Hidden`, while device, browser and OS analytics remain available.
