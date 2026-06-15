# Requirement Traceability Matrix — Version 4.2.0

| Requirement | Implementation | Automated evidence | Physical acceptance |
|---|---|---|---|
| One unchanged short URL | Flask gateway on short domain | route/gateway tests | Pending platform matrix |
| Evidence-based platform detection | package, UA, referrer, preview correlation | platform regression tests | Pending real app tests |
| Correct Android/Linux classification | touch/screen desktop-mode override | regression tests | Pending real Android repeat |
| Each device and click count | estimated-device grouping + device cards | cross-context merge tests | Pending user's phone test |
| Browser/app contexts visible | browser identity metric | merge regression tests | Pending user's phone test |
| Platform-wise analytics | global platform and surface views | endpoint/template tests | Pending platform matrix |
| Link-wise analytics | per-link live endpoint | route tests | Pending production traffic |
| Automatic background update | 1.5-second fetch polling | JS/template regression + endpoint tests | Pending public browser observation |
| Global understandable UI | executive summary/funnel/cards | Chromium desktop render | User acceptance pending |
| Mobile/tablet/browser optimization | responsive CSS | Chromium 390x844, 0px overflow | iPhone/iPad/Android physical pending |
| Debug/CI/CD/tests | pytest, coverage, Ruff, compile, pip check | 60 passed, 88% | N/A |
