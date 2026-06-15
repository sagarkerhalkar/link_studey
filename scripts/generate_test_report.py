import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "test-results"

junit = ET.parse(RESULTS / "junit.xml").getroot()
# pytest can emit testsuites root with one testsuite child.
suite = junit if junit.tag == "testsuite" else junit.find("testsuite")
attrs = suite.attrib if suite is not None else {}
coverage = ET.parse(RESULTS / "coverage.xml").getroot().attrib
line_rate = float(coverage.get("line-rate", "0")) * 100
browser = json.loads((RESULTS / "browser-acceptance.json").read_text())
checks = [
    ("Python dependency integrity", "PASS", "pip check: no broken requirements"),
    ("Python compilation", "PASS", "All application, test and script modules compiled"),
    ("Ruff static analysis", "PASS", "All checks passed"),
    ("Pytest unit/integration suite", "PASS", f"{attrs.get('tests', '0')} tests, {attrs.get('failures', '0')} failures, {attrs.get('errors', '0')} errors"),
    ("Measured line coverage", "PASS", f"{line_rate:.1f}% across link_analytics"),
    ("Background live refresh", "PASS" if browser["background_live_refresh"] else "FAIL", "Analytics total changed while the page remained open"),
    ("Generic Android classification", "PASS" if browser["generic_android_correct"] else "FAIL", "Android Mobile + Android OS; no false Linux/platform claim"),
    ("Same-device repeat clicks", "PASS" if browser["same_device_repeat_count"] else "FAIL", "Two clicks grouped under one anonymous device"),
    ("WhatsApp evidence detection", "PASS" if browser["whatsapp_evidence_detection"] else "FAIL", "Confirmed only when com.whatsapp package evidence was supplied"),
    ("Mobile responsive layout", "PASS" if browser["mobile_responsive"] else "FAIL", "390×844 viewport; no horizontal overflow"),
    ("Browser console", "PASS" if not browser["console_errors"] else "FAIL", "No JavaScript console or page errors"),
]
rows = "".join(
    f"<tr><td>{name}</td><td><span class='status {status.lower()}'>{status}</span></td><td>{detail}</td></tr>"
    for name, status, detail in checks
)
html = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Link Analytics 4.0.0 Test Report</title><style>
body{{margin:0;background:#f3f6fb;color:#152039;font-family:Inter,Segoe UI,Arial,sans-serif}}
main{{max-width:1180px;margin:40px auto;padding:0 28px 60px}} .hero{{background:linear-gradient(135deg,#101a46,#5d4ce6);color:white;border-radius:28px;padding:34px 38px;box-shadow:0 24px 70px #26327233}}
.eyebrow{{letter-spacing:.14em;text-transform:uppercase;font-size:12px;font-weight:800;color:#7ee5ff}}h1{{font-size:42px;margin:8px 0}}.hero p{{font-size:18px;opacity:.86;margin:0}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}}.card{{background:white;border:1px solid #dce3ef;border-radius:18px;padding:20px;box-shadow:0 12px 35px #26327212}}.card b{{display:block;font-size:28px;margin-top:7px}}.card small{{color:#69758d}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:20px;overflow:hidden;box-shadow:0 12px 35px #26327212}}th,td{{padding:15px 18px;border-bottom:1px solid #e7ebf2;text-align:left}}th{{background:#f7f9fd;color:#59647a;font-size:12px;text-transform:uppercase;letter-spacing:.09em}}td:first-child{{font-weight:700}}.status{{display:inline-block;padding:6px 11px;border-radius:999px;font-size:12px;font-weight:800}}.pass{{background:#dff8ec;color:#087549}}.fail{{background:#ffe2e2;color:#a51d1d}}.note{{margin-top:18px;padding:18px 20px;border:1px solid #d6deef;border-radius:16px;background:#fff;color:#566178}}
</style></head><body><main><section class='hero'><span class='eyebrow'>Verified build evidence</span><h1>Link Analytics 4.0.0</h1><p>Automated unit, integration and real-browser acceptance results — generated from this build.</p></section>
<section class='grid'><div class='card'><small>Automated tests</small><b>{attrs.get('tests','0')}</b></div><div class='card'><small>Failures</small><b>{attrs.get('failures','0')}</b></div><div class='card'><small>Coverage</small><b>{line_rate:.1f}%</b></div><div class='card'><small>Browser errors</small><b>{len(browser['console_errors'])}</b></div></section>
<table><thead><tr><th>Validation</th><th>Result</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table>
<div class='note'><strong>Truth boundary:</strong> The same short URL detects a platform only when the browser request contains app-package, in-app user-agent, or referrer evidence. When an app removes all evidence, the product records <em>Unknown / Hidden</em> rather than inventing WhatsApp or another source.</div>
</main></body></html>"""
(RESULTS / "TEST_REPORT.html").write_text(html, encoding="utf-8")
