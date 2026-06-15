import pytest

from link_analytics.analytics import aggregate_visits, detect_platform, normalize_visit


@pytest.mark.parametrize(
    ("package", "platform"),
    [
        ("com.whatsapp", "WhatsApp"),
        ("com.instagram.android", "Instagram"),
        ("org.telegram.messenger", "Telegram"),
        ("com.google.android.apps.dynamite", "Google Chat"),
        ("com.linkedin.android", "LinkedIn"),
        ("com.microsoft.teams", "Microsoft Teams"),
        ("com.twitter.android", "X / Twitter"),
    ],
)
def test_android_package_is_confirmed_platform(package, platform):
    result = detect_platform("", "Mozilla/5.0 (Linux; Android 14)", package)
    assert result[0] == platform
    assert result[1] == "Mobile app"
    assert result[2] == "Confirmed"
    assert package in result[3]


@pytest.mark.parametrize(
    ("referrer", "platform", "surface"),
    [
        ("https://web.whatsapp.com/", "WhatsApp", "Web"),
        ("https://l.instagram.com/", "Instagram", "App or web"),
        ("https://web.telegram.org/", "Telegram", "Web"),
        ("https://chat.google.com/", "Google Chat", "Web"),
        ("https://teams.microsoft.com/", "Microsoft Teams", "Web"),
    ],
)
def test_web_referrer_platform_detection(referrer, platform, surface):
    result = detect_platform(referrer, "Mozilla/5.0")
    assert result[:2] == (platform, surface)
    assert result[2] in {"Confirmed", "Strong"}


def test_plain_android_browser_never_becomes_linux_or_social_platform():
    row = normalize_visit(
        {
            "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/140 Mobile",
            "referrer": "",
            "cookie_id": "device-one",
            "client": {"platform": "Android", "mobile": True, "model": "Pixel 8"},
        }
    )
    assert row["platform"] == "Unknown / Hidden"
    assert row["os"] == "Android"
    assert row["device_label"] == "Android Mobile"
    assert row["model"] == "Pixel 8"


def test_ipad_desktop_user_agent_uses_touch_client_hint():
    row = normalize_visit(
        {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 Version/17 Safari/605.1.15",
            "cookie_id": "ipad-one",
            "client": {
                "platform": "macOS",
                "mobile": False,
                "maxTouchPoints": 5,
                "screenWidth": 1024,
                "screenHeight": 1366,
            },
        }
    )
    assert row["os"] == "iPadOS"
    assert row["device_label"] == "iPad"


def test_same_storage_id_groups_repeat_clicks():
    rows = [
        {
            "date": "2026-06-15T10:00:00Z",
            "user_agent": "Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile",
            "local_storage_id": "stable-device",
            "platform": "WhatsApp",
            "surface": "Mobile app",
            "confidence": "Confirmed",
            "client": {"platform": "Android", "mobile": True},
            "collection_status": "enriched",
        },
        {
            "date": "2026-06-15T10:01:00Z",
            "user_agent": "Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile",
            "local_storage_id": "stable-device",
            "platform": "Instagram",
            "surface": "Mobile app",
            "confidence": "Strong",
            "client": {"platform": "Android", "mobile": True},
            "collection_status": "enriched",
        },
        {
            "date": "2026-06-15T10:02:00Z",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140",
            "local_storage_id": "other-device",
            "platform": "WhatsApp",
            "surface": "Web",
            "confidence": "Confirmed",
            "client": {"platform": "Windows", "mobile": False},
            "collection_status": "enriched",
        },
    ]
    result = aggregate_visits(rows)
    assert result["total"] == 3
    assert result["unique_devices"] == 2
    assert result["repeat_clicks"] == 1
    first = next(item for item in result["device_rows"] if item["clicks"] == 2)
    assert {p["label"] for p in first["platforms"]} == {
        "WhatsApp · Mobile app",
        "Instagram · Mobile app",
    }


def test_mixed_timezone_and_missing_dates_are_safe():
    result = aggregate_visits(
        [
            {"date": "", "user_agent": "Mozilla/5.0", "cookie_id": "a", "collection_status": "enriched"},
            {"date": "2026-06-15T10:00:00+00:00", "user_agent": "Mozilla/5.0", "cookie_id": "b", "collection_status": "enriched"},
            {"date": "2026-06-15T11:00:00", "user_agent": "Mozilla/5.0", "cookie_id": "c", "collection_status": "enriched"},
        ]
    )
    assert result["total"] == 3
    assert result["recent"][0]["date"] in {
        "2026-06-15T10:00:00+00:00",
        "2026-06-15T11:00:00",
    }


def test_platform_identification_rate_excludes_hidden():
    result = aggregate_visits(
        [
            {"cookie_id": "a", "platform": "WhatsApp", "surface": "Mobile app", "confidence": "Confirmed", "collection_status": "enriched"},
            {"cookie_id": "b", "platform": "Unknown / Hidden", "surface": "Browser or app", "confidence": "Unavailable", "collection_status": "enriched"},
        ]
    )
    assert result["platform_identified"] == 1
    assert result["platform_hidden"] == 1
    assert result["platform_identification_rate"] == 50.0


def test_linux_desktop_mode_with_mobile_touch_screen_is_probable_android():
    row = normalize_visit(
        {
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36",
            "cookie_id": "desktop-mode-android",
            "collection_status": "enriched",
            "client": {
                "platform": "Linux",
                "mobile": False,
                "maxTouchPoints": 5,
                "screenWidth": 412,
                "screenHeight": 915,
                "pixelRatio": 2.75,
            },
        }
    )
    assert row["device_label"] == "Android Mobile"
    assert row["os"] == "Android"
    assert row["device_confidence"] == "Probable"
    assert "desktop-site" in row["device_evidence"]


def test_whatsapp_preview_correlates_hidden_external_browser_click_as_probable():
    result = aggregate_visits(
        [
            {
                "date": "2026-06-15T11:45:48+00:00",
                "user_agent": "WhatsApp/2.23.20.0",
                "is_bot": True,
                "platform": "WhatsApp",
                "surface": "Preview service",
                "confidence": "Strong",
                "collection_status": "server-only",
            },
            {
                "date": "2026-06-15T11:46:02+00:00",
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36",
                "cookie_id": "phone-in-desktop-mode",
                "collection_status": "enriched",
                "client": {
                    "platform": "Linux",
                    "mobile": False,
                    "maxTouchPoints": 5,
                    "screenWidth": 412,
                    "screenHeight": 915,
                    "pixelRatio": 2.75,
                },
            },
        ]
    )
    assert result["total"] == 1
    assert result["preview_requests"] == 1
    assert result["platforms"] == [("WhatsApp", 1)]
    click = result["recent"][0]
    assert click["platform"] == "WhatsApp"
    assert click["confidence"] == "Probable"
    assert click["device_label"] == "Android Mobile"
    assert click["os"] == "Android"


def test_server_only_non_bot_is_excluded_from_device_and_click_totals():
    result = aggregate_visits(
        [
            {
                "date": "2026-06-15T11:00:00Z",
                "user_agent": "Mozilla/5.0 (Linux; Android 15) Chrome/149 Mobile",
                "cookie_id": "incomplete",
                "collection_status": "server-only",
                "is_bot": False,
            }
        ]
    )
    assert result["total"] == 0
    assert result["unique_devices"] == 0
    assert result["devices"] == []
    assert result["unverified_requests"] == 1
