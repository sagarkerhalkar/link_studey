# Solution for the Android / WhatsApp / Linux issue — Version 4.1.0

## Root cause proven by the real diagnostic

The diagnostic contained three different request types:

1. Instagram WebView requests with package/referrer evidence — correctly identified as Android Mobile and Instagram.
2. WhatsApp preview requests — identifiable, server-only and bot-like.
3. The external browser opened after WhatsApp — presented a Linux/X11 desktop user-agent and hid direct WhatsApp evidence.

The earlier build treated item 3 as Linux Desktop and did not connect it to the immediately preceding WhatsApp preview.

## Implemented solution

- Count only enriched human browser events as verified clicks.
- Keep preview/bot and incomplete events separate.
- Use touch points, screen size and pixel ratio to detect Android desktop-site mode behind Linux/X11 user-agents.
- Correlate a hidden browser click with the nearest identifiable platform preview for the same short link within 120 seconds.
- Label correlated results `Probable`; direct package/referrer/in-app evidence remains `Confirmed` or `Strong`.
- Group repeat clicks using first-party cookie/localStorage identity.
- Continue background live polling without reloading the page.

## Expected result for the reported sequence

```text
WhatsApp preview request        -> Preview/bot count only
External Chrome mobile click    -> Android Mobile (Probable device evidence)
Platform                        -> WhatsApp (Probable, recent preview evidence)
Second click same browser       -> Same device row; click count increases
Linux Desktop                   -> 0 for the mobile desktop-site request
```

## Limitation

If an application supplies no direct app evidence and no identifiable preview occurs, the platform cannot be proven from one unchanged URL. The result remains `Unknown / Hidden` rather than a fabricated platform.
