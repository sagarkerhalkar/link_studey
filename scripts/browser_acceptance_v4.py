import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:24131")
OUT = Path(os.getenv("ARTIFACTS", "test-results/screenshots"))
OUT.mkdir(parents=True, exist_ok=True)
CHROMIUM = os.getenv("BROWSER_EXECUTABLE", "/usr/bin/chromium")


def login(page):
    page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    page.locator("input[name=username]").fill("admin")
    page.locator("input[name=password]").fill("AdminPassword123!")
    page.locator("button[type=submit], input[type=submit]").click()
    page.wait_for_url("**/dashboard")


def create_link(page, tag):
    page.goto(f"{BASE_URL}/links/new", wait_until="networkidle")
    page.locator("[name=destination_url]").fill(f"{BASE_URL}/privacy")
    page.locator("[name=custom_tag]").fill(tag)
    page.locator("button[type=submit], input[type=submit]").last.click()
    page.wait_for_url("**/analytics")


def metric(page, key):
    return page.locator(f'[data-live-value="{key}"]').first


def main():
    results = {
        "desktop_login": False,
        "single_link_created": False,
        "generic_android_correct": False,
        "same_device_repeat_count": False,
        "cross_context_device_merge": False,
        "whatsapp_evidence_detection": False,
        "whatsapp_preview_external_browser_probable": False,
        "linux_desktop_mode_corrected_to_android": False,
        "background_live_refresh": False,
        "global_analytics_ui": False,
        "mobile_responsive": False,
        "console_errors": [],
    }

    with sync_playwright() as pw:
        launch_options = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--no-proxy-server",
                "--proxy-bypass-list=*",
                "--disable-features=BlockInsecurePrivateNetworkRequests",
            ],
        }
        if CHROMIUM and Path(CHROMIUM).exists():
            launch_options["executable_path"] = CHROMIUM
        browser = pw.chromium.launch(**launch_options)
        desktop = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = desktop.new_page()
        page.on(
            "console",
            lambda msg: results["console_errors"].append(msg.text)
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: results["console_errors"].append(str(error)))

        login(page)
        results["desktop_login"] = True
        tag = "acceptance-v42"
        create_link(page, tag)
        results["single_link_created"] = True
        expect(metric(page, "total")).to_have_text("0")
        expect(page.get_by_text("From request to real audience")).to_be_visible()
        expect(page.get_by_text("One device, all its clicks and platforms")).to_be_visible()
        results["global_analytics_ui"] = True

        android_ua = (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
            "AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36"
        )
        android = browser.new_context(
            viewport={"width": 412, "height": 915},
            user_agent=android_ua,
            device_scale_factor=2.625,
            is_mobile=True,
            has_touch=True,
        )
        phone = android.new_page()
        phone.goto(f"{BASE_URL}/r/{tag}", wait_until="networkidle")

        # The analytics tab stays open and changes without a page reload.
        expect(metric(page, "total")).to_have_text("1", timeout=7000)
        expect(metric(page, "estimated_devices")).to_have_text("1")
        results["background_live_refresh"] = True
        expect(page.locator("[data-live-device-cards]").first).to_contain_text(
            "Android Mobile"
        )
        expect(page.locator("[data-live-recent-cards]").first).to_contain_text(
            "Unknown / Hidden"
        )
        results["generic_android_correct"] = True

        phone.goto(f"{BASE_URL}/r/{tag}", wait_until="networkidle")
        expect(metric(page, "total")).to_have_text("2", timeout=7000)
        expect(metric(page, "estimated_devices")).to_have_text("1")
        expect(metric(page, "repeat_clicks")).to_have_text("1")
        results["same_device_repeat_count"] = True

        # A separate in-app browser context on the same simulated hardware must
        # count as a second browser identity but the same estimated device.
        whatsapp = browser.new_context(
            viewport={"width": 412, "height": 915},
            user_agent=android_ua,
            device_scale_factor=2.625,
            is_mobile=True,
            has_touch=True,
            extra_http_headers={"X-Requested-With": "com.whatsapp"},
        )
        whatsapp_page = whatsapp.new_page()
        whatsapp_page.goto(f"{BASE_URL}/r/{tag}", wait_until="networkidle")
        expect(metric(page, "total")).to_have_text("3", timeout=7000)
        expect(metric(page, "estimated_devices")).to_have_text("1")
        expect(metric(page, "browser_identities")).to_have_text("2")
        expect(page.locator("[data-live-device-cards]").first).to_contain_text(
            "3 clicks"
        )
        results["cross_context_device_merge"] = True
        expect(page.locator("[data-live-recent-cards]").first).to_contain_text(
            "WhatsApp"
        )
        expect(page.locator("[data-live-recent-cards]").first).to_contain_text(
            "Android app package"
        )
        results["whatsapp_evidence_detection"] = True

        # Regression for the real field pattern: preview first, then Android
        # Chrome desktop-site mode with X11/Linux and no direct app referrer.
        preview_tag = "acceptance-v42-preview"
        create_link(page, preview_tag)
        preview_response = desktop.request.get(
            f"{BASE_URL}/r/{preview_tag}",
            headers={"User-Agent": "WhatsApp/2.23.20.0"},
        )
        assert preview_response.status in {200, 302}

        desktop_mode = browser.new_context(
            viewport={"width": 412, "height": 915},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
            ),
            device_scale_factor=2.75,
            is_mobile=True,
            has_touch=True,
        )
        desktop_mode_page = desktop_mode.new_page()
        desktop_mode_page.goto(f"{BASE_URL}/r/{preview_tag}", wait_until="networkidle")
        expect(metric(page, "total")).to_have_text("1", timeout=7000)
        expect(page.locator("[data-live-recent-cards]").first).to_contain_text(
            "Android Mobile"
        )
        expect(page.locator("[data-live-recent-cards]").first).to_contain_text(
            "WhatsApp"
        )
        expect(page.locator("[data-live-recent-cards]").first).to_contain_text(
            "Probable"
        )
        expect(page.locator("[data-live-recent-cards]").first).not_to_contain_text(
            "Linux Desktop"
        )
        results["linux_desktop_mode_corrected_to_android"] = True
        results["whatsapp_preview_external_browser_probable"] = True

        page.screenshot(path=OUT / "01_desktop_global_analytics_v42.png", full_page=True)

        mobile_dashboard = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )
        mobile_page = mobile_dashboard.new_page()
        login(mobile_page)
        mobile_page.goto(page.url, wait_until="networkidle")
        overflow = mobile_page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 2, f"Mobile horizontal overflow: {overflow}px"
        expect(mobile_page.locator("h1")).to_be_visible()
        expect(mobile_page.get_by_text("Traffic overview")).to_be_visible()
        mobile_page.screenshot(
            path=OUT / "02_mobile_global_analytics_v42.png", full_page=True
        )
        results["mobile_responsive"] = True

        results["console_errors"] = list(dict.fromkeys(results["console_errors"]))
        assert not results["console_errors"], results["console_errors"]
        (OUT.parent / "browser-acceptance-v42.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        browser.close()


if __name__ == "__main__":
    main()
