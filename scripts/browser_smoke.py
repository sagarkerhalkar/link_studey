import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:2331")
BROWSER = os.getenv("BROWSER", "chromium")
ARTIFACTS = Path(os.getenv("ARTIFACTS", "test-results")) / BROWSER
ARTIFACTS.mkdir(parents=True, exist_ok=True)

VIEWPORTS = {
    "iphone": {"width": 390, "height": 844},
    "ipad": {"width": 820, "height": 1180},
    "laptop": {"width": 1366, "height": 768},
    "desktop": {"width": 1600, "height": 1000},
}


def assert_no_overflow(page):
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 2, f"Horizontal overflow detected: {overflow}px at {page.url}"


def main():
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, BROWSER)
        executable_path = os.getenv("BROWSER_EXECUTABLE")
        launch_options = {"executable_path": executable_path} if executable_path else {}
        browser = browser_type.launch(**launch_options)
        for name, options in VIEWPORTS.items():
            context = browser.new_context(
                viewport={"width": options["width"], "height": options["height"]},
            )
            page = context.new_page()
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))

            page.goto(BASE_URL, wait_until="networkidle")
            assert page.locator("h1").is_visible()
            assert_no_overflow(page)
            hero_size = float(page.locator("h1").evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
            assert 30 <= hero_size <= 74, f"Hero font size is not balanced: {hero_size}px"

            initial_theme = page.locator("html").get_attribute("data-theme")
            page.locator("[data-theme-toggle]").first.click()
            changed_theme = page.locator("html").get_attribute("data-theme")
            assert changed_theme != initial_theme

            page.goto(f"{BASE_URL}/login", wait_until="networkidle")
            assert_no_overflow(page)
            login_size = float(page.locator(".auth-card h2").evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
            assert 22 <= login_size <= 36, f"Login heading is not balanced: {login_size}px"
            page.locator("input[name=username]").fill("admin")
            page.locator("input[name=password]").fill("AdminPassword123!")
            page.locator("button[type=submit], input[type=submit]").click()
            page.wait_for_url("**/dashboard")
            assert_no_overflow(page)

            page.goto(f"{BASE_URL}/links/new", wait_until="networkidle")
            assert page.locator("[name=destination_url]").count() == 1
            assert page.locator("[name=custom_tag]").count() == 1
            assert page.locator("[name=slug]").count() == 0
            assert page.locator("[name=share_tag]").count() == 0
            assert_no_overflow(page)
            page.locator("[name=destination_url]").fill("https://example.com/a/very/long/url")
            tag = f"ci{name}{BROWSER}".replace("-", "")[:40]
            page.locator("[name=custom_tag]").fill(tag)
            preview = page.locator("#short-preview").inner_text()
            assert preview == f"https://s.sagarkerhalkar.com/{tag}"
            page.locator("input[type=submit], button[type=submit]").last.click()
            page.wait_for_url("**/analytics")
            assert page.get_by_text(f"https://s.sagarkerhalkar.com/{tag}", exact=True).first.is_visible()
            assert page.get_by_text("One unchanged short URL", exact=False).is_visible()
            assert page.locator('[data-copy*="?src="]').count() == 0
            assert page.locator('[data-live-analytics]').count() == 1
            assert_no_overflow(page)

            page.screenshot(path=ARTIFACTS / f"{name}.png", full_page=True)
            assert not errors, f"Browser console errors: {errors}"
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
