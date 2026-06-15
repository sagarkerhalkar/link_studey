import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from playwright.sync_api import sync_playwright

from link_analytics import create_app
from link_analytics.extensions import db
from link_analytics.models import GatewayClickEvent, ManagedLink, User

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-results" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


class FakeShlink:
    def health(self):
        return {"status": "pass", "version": "visual-test"}

    def get_short_url(self, _code):
        return {"visitsSummary": {"total": 0, "nonBots": 0, "bots": 0}}

    def get_visits(self, _code, page=1, items_per_page=1000):
        del page, items_per_page
        return []


def add_event(link_id, *, cookie, local, signature, ip, platform, surface, confidence,
              evidence, ua, client, browser=None, os_family=None, model=None,
              bot=False, status="enriched", seconds=0):
    from datetime import datetime, timedelta, timezone

    event = GatewayClickEvent(
        click_token=uuid4().hex,
        managed_link_id=link_id,
        cookie_id=cookie,
        local_storage_id=local,
        fingerprint_hash=uuid4().hex,
        ip_hash=ip,
        request_host="s.sagarkerhalkar.com",
        user_agent=ua,
        platform=platform,
        surface=surface,
        confidence=confidence,
        evidence=evidence,
        browser=browser,
        os_family=os_family,
        model=model,
        country="IN",
        region="Madhya Pradesh",
        city="Bhopal",
        is_bot=bot,
        collected=status == "enriched",
        collection_status=status,
        client_payload=json.dumps({**client, "deviceSignatureHash": signature}),
        created_at=datetime.now(timezone.utc) + timedelta(seconds=seconds),
    )
    db.session.add(event)


def inline_assets(html: str) -> str:
    css = (ROOT / "link_analytics/static/css/app.css").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="/static/css/app.css">',
        f"<style>{css}</style>",
    )
    html = html.replace('<script src="/static/js/theme-init.js"></script>', '')
    html = html.replace('<script src="/static/js/app.js" defer></script>', '')
    html = html.replace('data-theme="system"', 'data-theme="light"')
    return html


def main():
    with TemporaryDirectory() as temp:
        fake = FakeShlink()
        app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "visual-report-secret",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(temp, 'visual.db').as_posix()}",
                "AUTO_CREATE_DB": True,
                "SHLINK_CLIENT_FACTORY": lambda: fake,
                "SHLINK_DOMAIN": "s.sagarkerhalkar.com",
                "PUBLIC_SHORT_BASE_URL": "https://s.sagarkerhalkar.com",
                "SESSION_COOKIE_SECURE": False,
            }
        )
        with app.app_context():
            admin = User(username="admin", display_name="Sagar Kerhalkar", role="admin", is_active=True)
            admin.set_password("AdminPassword123!")
            db.session.add(admin)
            db.session.flush()
            link = ManagedLink(
                owner_id=admin.id,
                custom_tag="global-campaign-2026",
                short_code="global-campaign-2026",
                domain="s.sagarkerhalkar.com",
                short_url="https://s.sagarkerhalkar.com/global-campaign-2026",
                long_url="https://example.com/global-campaign",
                is_active=True,
            )
            db.session.add(link)
            db.session.flush()

            android = {
                "platform": "Android", "mobile": True, "model": "CPH2491",
                "screenWidth": 412, "screenHeight": 915, "pixelRatio": 2.625,
                "maxTouchPoints": 5, "hardwareConcurrency": 8, "deviceMemory": 8,
                "timezone": "Asia/Kolkata", "language": "en-IN",
            }
            samsung = {
                "platform": "Android", "mobile": True, "model": "SM-A156E",
                "screenWidth": 384, "screenHeight": 854, "pixelRatio": 2.8,
                "maxTouchPoints": 5, "hardwareConcurrency": 8, "deviceMemory": 6,
                "timezone": "Asia/Kolkata", "language": "en-IN",
            }
            windows = {
                "platform": "Windows", "mobile": False, "model": "",
                "screenWidth": 1920, "screenHeight": 1080, "pixelRatio": 1,
                "maxTouchPoints": 0, "hardwareConcurrency": 12, "deviceMemory": 16,
                "timezone": "Asia/Kolkata", "language": "en-IN",
            }
            iphone = {
                "platform": "iOS", "mobile": True, "model": "iPhone",
                "screenWidth": 393, "screenHeight": 852, "pixelRatio": 3,
                "maxTouchPoints": 5, "hardwareConcurrency": 6, "deviceMemory": 4,
                "timezone": "Asia/Kolkata", "language": "en-IN",
            }

            android_ua = "Mozilla/5.0 (Linux; Android 16; CPH2491) AppleWebKit/537.36 Chrome/149 Mobile Safari/537.36"
            add_event(link.id, cookie="a1", local="chrome-a", signature="sig-a", ip="ip-a", platform="WhatsApp", surface="Mobile app", confidence="Confirmed", evidence="Android app package: com.whatsapp", ua=android_ua, client=android, seconds=1)
            add_event(link.id, cookie="a2", local="telegram-a", signature="sig-a", ip="ip-a", platform="Telegram", surface="Mobile app", confidence="Confirmed", evidence="Android app package: org.telegram.messenger", ua=android_ua, client=android, seconds=2)
            add_event(link.id, cookie="a1", local="chrome-a", signature="sig-a", ip="ip-a", platform="Unknown / Hidden", surface="Browser or app", confidence="Hidden", evidence="Launching application removed platform evidence", ua=android_ua, client=android, seconds=3)
            add_event(link.id, cookie="a3", local="instagram-a", signature="sig-a", ip="ip-a", platform="Instagram", surface="Mobile app", confidence="Confirmed", evidence="Android app package: com.instagram.android", ua=android_ua, client=android, seconds=4)

            samsung_ua = "Mozilla/5.0 (Linux; Android 15; SM-A156E) AppleWebKit/537.36 SamsungBrowser/27 Mobile Safari/537.36"
            add_event(link.id, cookie="b1", local="samsung-b", signature="sig-b", ip="ip-b", platform="Unknown / Hidden", surface="Browser or app", confidence="Hidden", evidence="Launching application removed platform evidence", ua=samsung_ua, client=samsung, seconds=5)

            windows_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149 Safari/537.36"
            add_event(link.id, cookie="c1", local="chrome-c", signature="sig-c", ip="ip-c", platform="Telegram", surface="Web", confidence="Confirmed", evidence="Referrer domain: web.telegram.org", ua=windows_ua, client=windows, seconds=6)
            add_event(link.id, cookie="c1", local="chrome-c", signature="sig-c", ip="ip-c", platform="WhatsApp", surface="Web", confidence="Confirmed", evidence="Referrer domain: web.whatsapp.com", ua=windows_ua, client=windows, seconds=7)
            add_event(link.id, cookie="c2", local="edge-c", signature="sig-c", ip="ip-c", platform="LinkedIn", surface="Web", confidence="Confirmed", evidence="Referrer domain: linkedin.com", ua=windows_ua, client=windows, seconds=8)

            iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
            add_event(link.id, cookie="d1", local="safari-d", signature="sig-d", ip="ip-d", platform="Google Chat", surface="Mobile app", confidence="Probable", evidence="Google Chat preview preceded browser launch", ua=iphone_ua, client=iphone, seconds=9)

            add_event(link.id, cookie="bot1", local="", signature="", ip="bot-ip", platform="WhatsApp", surface="Preview service", confidence="Strong", evidence="Platform preview signature: whatsapp", ua="WhatsApp/2.24", client={}, bot=True, status="server-only", seconds=-1)
            add_event(link.id, cookie="bot2", local="", signature="", ip="bot-ip2", platform="Telegram", surface="Preview service", confidence="Strong", evidence="Platform preview signature: telegrambot", ua="TelegramBot/1.0", client={}, bot=True, status="server-only", seconds=0)
            db.session.commit()
            link_id = link.id

        client = app.test_client()
        client.post("/login", data={"username": "admin", "password": "AdminPassword123!"})
        response = client.get(f"/links/{link_id}/analytics")
        assert response.status_code == 200
        html = inline_assets(response.get_data(as_text=True))
        (ROOT / "test-results/visual-analytics-v42.html").write_text(html, encoding="utf-8")

        results = {"desktop": False, "mobile": False, "mobile_overflow_px": None, "console_errors": []}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.on("console", lambda msg: results["console_errors"].append(msg.text) if msg.type == "error" else None)
            page.set_content(html, wait_until="load")
            assert page.get_by_text("From request to real audience").is_visible()
            assert page.get_by_text("One device, all its clicks and platforms").is_visible()
            page.screenshot(path=OUT / "01_desktop_global_analytics_v42.png", full_page=True)
            results["desktop"] = True

            mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
            mobile.set_content(html, wait_until="load")
            overflow = mobile.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            results["mobile_overflow_px"] = overflow
            assert overflow <= 2, f"Mobile horizontal overflow: {overflow}px"
            assert mobile.get_by_text("Traffic overview").is_visible()
            mobile.screenshot(path=OUT / "02_mobile_global_analytics_v42.png", full_page=True)
            results["mobile"] = True
            browser.close()

        (ROOT / "test-results/visual-browser-v42.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        assert not results["console_errors"], results["console_errors"]


if __name__ == "__main__":
    main()
