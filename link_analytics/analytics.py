from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse

from user_agents import parse as parse_user_agent


PLATFORM_DOMAINS: dict[str, tuple[str, str, str]] = {
    "web.whatsapp.com": ("WhatsApp", "Web", "Confirmed"),
    "whatsapp.com": ("WhatsApp", "Web", "Strong"),
    "l.instagram.com": ("Instagram", "App or web", "Strong"),
    "instagram.com": ("Instagram", "Web", "Confirmed"),
    "m.facebook.com": ("Facebook", "Mobile web", "Confirmed"),
    "l.facebook.com": ("Facebook", "App or web", "Strong"),
    "lm.facebook.com": ("Facebook", "App or web", "Strong"),
    "facebook.com": ("Facebook", "Web", "Confirmed"),
    "messenger.com": ("Messenger", "Web", "Confirmed"),
    "linkedin.com": ("LinkedIn", "Web", "Confirmed"),
    "lnkd.in": ("LinkedIn", "Web", "Strong"),
    "t.co": ("X / Twitter", "App or web", "Strong"),
    "twitter.com": ("X / Twitter", "Web", "Confirmed"),
    "x.com": ("X / Twitter", "Web", "Confirmed"),
    "web.telegram.org": ("Telegram", "Web", "Confirmed"),
    "telegram.org": ("Telegram", "Web", "Strong"),
    "t.me": ("Telegram", "App or web", "Strong"),
    "chat.google.com": ("Google Chat", "Web", "Confirmed"),
    "mail.google.com": ("Gmail", "Web", "Confirmed"),
    "youtube.com": ("YouTube", "Web", "Confirmed"),
    "youtu.be": ("YouTube", "App or web", "Strong"),
    "discord.com": ("Discord", "Web", "Confirmed"),
    "slack.com": ("Slack", "Web", "Confirmed"),
    "teams.microsoft.com": ("Microsoft Teams", "Web", "Confirmed"),
    "teams.live.com": ("Microsoft Teams", "Web", "Confirmed"),
    "tiktok.com": ("TikTok", "Web", "Confirmed"),
    "snapchat.com": ("Snapchat", "Web", "Confirmed"),
    "reddit.com": ("Reddit", "Web", "Confirmed"),
    "pinterest.com": ("Pinterest", "Web", "Confirmed"),
    "threads.net": ("Threads", "Web", "Confirmed"),
}

# Android WebView often exposes the launching package through X-Requested-With.
# This is the strongest automatic same-URL signal available when present.
ANDROID_PACKAGE_MAP: dict[str, tuple[str, str]] = {
    "com.whatsapp": ("WhatsApp", "Mobile app"),
    "com.whatsapp.w4b": ("WhatsApp Business", "Mobile app"),
    "com.instagram.android": ("Instagram", "Mobile app"),
    "com.facebook.katana": ("Facebook", "Mobile app"),
    "com.facebook.lite": ("Facebook Lite", "Mobile app"),
    "com.facebook.orca": ("Messenger", "Mobile app"),
    "org.telegram.messenger": ("Telegram", "Mobile app"),
    "org.telegram.messenger.web": ("Telegram", "Mobile app"),
    "org.thunderdog.challegram": ("Telegram X", "Mobile app"),
    "com.linkedin.android": ("LinkedIn", "Mobile app"),
    "com.twitter.android": ("X / Twitter", "Mobile app"),
    "com.google.android.apps.dynamite": ("Google Chat", "Mobile app"),
    "com.google.android.gm": ("Gmail", "Mobile app"),
    "com.google.android.youtube": ("YouTube", "Mobile app"),
    "com.microsoft.teams": ("Microsoft Teams", "Mobile app"),
    "com.microsoft.teams2": ("Microsoft Teams", "Mobile app"),
    "com.discord": ("Discord", "Mobile app"),
    "com.slack": ("Slack", "Mobile app"),
    "com.zhiliaoapp.musically": ("TikTok", "Mobile app"),
    "com.snapchat.android": ("Snapchat", "Mobile app"),
    "com.reddit.frontpage": ("Reddit", "Mobile app"),
    "com.pinterest": ("Pinterest", "Mobile app"),
    "org.signal": ("Signal", "Mobile app"),
    "com.viber.voip": ("Viber", "Mobile app"),
    "com.tencent.mm": ("WeChat", "Mobile app"),
    "jp.naver.line.android": ("LINE", "Mobile app"),
    "com.skype.raider": ("Skype", "Mobile app"),
}

UA_MARKERS: tuple[tuple[str, tuple[str, str]], ...] = (
    ("instagram", ("Instagram", "Mobile app")),
    ("fban/", ("Facebook", "Mobile app")),
    ("fbav/", ("Facebook", "Mobile app")),
    ("fb_iab", ("Facebook", "Mobile app")),
    ("messenger", ("Messenger", "Mobile app")),
    ("linkedinapp", ("LinkedIn", "Mobile app")),
    ("twitterandroid", ("X / Twitter", "Mobile app")),
    ("twitter for iphone", ("X / Twitter", "Mobile app")),
    ("telegram", ("Telegram", "Mobile app")),
    ("whatsapp", ("WhatsApp", "Mobile app")),
    ("googlechat", ("Google Chat", "Mobile app")),
    ("gmail", ("Gmail", "Mobile app")),
    ("discord", ("Discord", "Mobile app")),
    ("slack", ("Slack", "Mobile app")),
    ("teamsmobile", ("Microsoft Teams", "Mobile app")),
    ("tiktok", ("TikTok", "Mobile app")),
    ("snapchat", ("Snapchat", "Mobile app")),
    ("reddit", ("Reddit", "Mobile app")),
    ("pinterest", ("Pinterest", "Mobile app")),
    ("signal", ("Signal", "Mobile app")),
    ("micromessenger", ("WeChat", "Mobile app")),
    ("viber", ("Viber", "Mobile app")),
    ("skype", ("Skype", "Mobile app")),
    (" line/", ("LINE", "Mobile app")),
)

PREVIEW_UA_MARKERS: tuple[tuple[str, tuple[str, str]], ...] = (
    ("facebookexternalhit", ("Facebook", "Preview service")),
    ("facebot", ("Facebook", "Preview service")),
    ("telegrambot", ("Telegram", "Preview service")),
    ("linkedinbot", ("LinkedIn", "Preview service")),
    ("twitterbot", ("X / Twitter", "Preview service")),
    ("slackbot", ("Slack", "Preview service")),
    ("discordbot", ("Discord", "Preview service")),
)

PREVIEW_CORRELATION_WINDOW_SECONDS = 120



def _safe_text(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""
    return str(value)[:limit]


def _domain_source(referrer: str) -> tuple[str, str, str, str] | None:
    if not referrer:
        return None
    parsed = urlparse(referrer)
    if parsed.scheme == "android-app":
        package = (parsed.hostname or parsed.netloc or "").lower()
        if package in ANDROID_PACKAGE_MAP:
            platform, surface = ANDROID_PACKAGE_MAP[package]
            return platform, surface, "Confirmed", f"Android app package: {package}"
    host = (parsed.hostname or "").lower().removeprefix("www.")
    for domain, (platform, surface, confidence) in PLATFORM_DOMAINS.items():
        normalized = domain.removeprefix("www.")
        if host == normalized or host.endswith(f".{normalized}"):
            return platform, surface, confidence, f"Referrer domain: {host}"
    if host:
        return host, "External website", "Confirmed", f"Referrer domain: {host}"
    return None


def detect_platform(
    referrer: str | None,
    user_agent: str | None,
    x_requested_with: str | None = None,
    document_referrer: str | None = None,
) -> tuple[str, str, str, str]:
    """Best-effort automatic same-link platform detection.

    The detector never turns Android, Linux, Chrome, Safari, an IP address, or a
    device type into a social-platform claim. It reports a platform only when
    the request contains evidence: Android package, app-specific user-agent, or
    referrer. Apps that intentionally remove all three are shown as hidden.
    """
    package = _safe_text(x_requested_with, 300).strip().lower()
    if package in ANDROID_PACKAGE_MAP:
        platform, surface = ANDROID_PACKAGE_MAP[package]
        return platform, surface, "Confirmed", f"Android app package: {package}"

    for candidate in (_safe_text(document_referrer), _safe_text(referrer)):
        result = _domain_source(candidate.strip())
        if result:
            return result

    lower_ua = _safe_text(user_agent, 2000).lower()
    for marker, (platform, surface) in PREVIEW_UA_MARKERS:
        if marker in lower_ua:
            return platform, surface, "Strong", f"Platform preview signature: {marker.strip()}"

    for marker, (platform, surface) in UA_MARKERS:
        if marker in lower_ua:
            return platform, surface, "Strong", f"In-app browser signature: {marker.strip()}"

    return (
        "Unknown / Hidden",
        "Browser or app",
        "Hidden",
        "Launching application removed platform evidence",
    )


def detect_source(
    referrer: str | None,
    user_agent: str | None,
    source_hint: str | None = None,
):
    """Compatibility wrapper returning platform, surface and confidence.

    ``source_hint`` is intentionally ignored. Version 3 uses one unchanged URL
    and no source-specific query parameters.
    """
    del source_hint
    platform, surface, confidence, _evidence = detect_platform(referrer, user_agent)
    return platform, surface, confidence


def _client_value(client: dict[str, Any], key: str, default: Any = "") -> Any:
    value = client.get(key, default) if isinstance(client, dict) else default
    return value if value is not None else default


def _device_details(user_agent: str, client: dict[str, Any] | None = None):
    """Classify the browser device using UA plus browser-side evidence.

    Mobile browsers can request a desktop site and then expose an X11/Linux UA.
    In that case touch points, screen geometry and pixel ratio are stronger than
    the desktop-looking UA. We report Android as *probable*, never confirmed,
    unless Android is explicitly present in UA or client hints.
    """
    client = client or {}
    parsed = parse_user_agent(user_agent or "")
    lower_ua = (user_agent or "").lower()
    ch_platform = _safe_text(_client_value(client, "platform"), 120)
    ch_model = _safe_text(_client_value(client, "model"), 160)
    raw_mobile_hint = _client_value(client, "mobile", None)
    if isinstance(raw_mobile_hint, str):
        mobile_hint = raw_mobile_hint.strip().lower() in {"1", "true", "?1", "yes"}
    else:
        mobile_hint = bool(raw_mobile_hint) if raw_mobile_hint is not None else None

    def _to_int(value: Any) -> int:
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return 0

    def _to_float(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    max_touch = _to_int(_client_value(client, "maxTouchPoints", 0))
    screen_width = _to_int(_client_value(client, "screenWidth", 0))
    screen_height = _to_int(_client_value(client, "screenHeight", 0))
    pixel_ratio = _to_float(_client_value(client, "pixelRatio", 0))
    short_edge = min(v for v in (screen_width, screen_height) if v > 0) if screen_width and screen_height else 0
    long_edge = max(screen_width, screen_height)

    explicit_android = "android" in lower_ua or ch_platform.lower() == "android"
    explicit_ios = any(token in lower_ua for token in ("iphone", "cpu iphone os"))
    explicit_ipad = "ipad" in lower_ua
    platform_l = ch_platform.lower()

    # Desktop-site mode on Android commonly exposes X11/Linux and ?0. Browser
    # side touch/screen evidence is therefore allowed to override Linux Desktop.
    linux_desktop_ua = ("x11" in lower_ua or "linux" in lower_ua or platform_l == "linux") and not explicit_android
    phone_shape = (
        linux_desktop_ua
        and max_touch >= 2
        and 0 < short_edge <= 700
        and 0 < long_edge <= 1600
        and (pixel_ratio >= 1.25 or long_edge <= 1000)
    )
    tablet_shape = (
        linux_desktop_ua
        and max_touch >= 2
        and 600 < short_edge <= 1100
        and 0 < long_edge <= 1800
        and pixel_ratio >= 1.25
    )
    probable_android_desktop_mode = phone_shape or tablet_shape

    os_family = parsed.os.family or "Unknown"
    device_confidence = "Confirmed"
    device_evidence = "User-Agent or client platform"

    if explicit_android:
        os_family = "Android"
    elif probable_android_desktop_mode:
        os_family = "Android"
        device_confidence = "Probable"
        device_evidence = (
            f"Linux desktop-site UA with touch={max_touch}, screen={screen_width}x{screen_height}, "
            f"pixelRatio={pixel_ratio:g}"
        )
    elif explicit_ios:
        os_family = "iOS"
    elif explicit_ipad:
        os_family = "iPadOS"
    elif platform_l in {"ios", "ipados"}:
        os_family = "iPadOS" if max_touch > 1 and screen_width >= 700 else "iOS"
    elif "cros" in lower_ua or platform_l == "chrome os":
        os_family = "ChromeOS"
    elif "windows" in lower_ua or platform_l == "windows":
        os_family = "Windows"
    elif "macintosh" in lower_ua or "mac os x" in lower_ua or platform_l == "macos":
        os_family = "iPadOS" if max_touch > 1 else "macOS"
        if os_family == "iPadOS":
            device_confidence = "Probable"
            device_evidence = "Macintosh desktop-site UA with multi-touch capability"
    elif "linux" in lower_ua or platform_l == "linux":
        os_family = "Linux"

    if os_family == "Android":
        is_mobile = phone_shape or bool(mobile_hint) or "mobile" in lower_ua
        device_type = "Mobile" if is_mobile else "Tablet"
    elif os_family == "iPadOS" or explicit_ipad or parsed.is_tablet:
        device_type = "Tablet"
    elif os_family == "iOS" or explicit_ios or parsed.is_mobile:
        device_type = "Mobile"
    elif max_touch > 1 and short_edge and short_edge <= 1100 and os_family not in {"Windows", "macOS", "ChromeOS"}:
        device_type = "Tablet"
    elif max_touch > 0 and short_edge and short_edge <= 700 and os_family == "Unknown":
        device_type = "Mobile"
    elif parsed.is_pc or os_family in {"Windows", "macOS", "ChromeOS", "Linux"}:
        device_type = "Desktop"
    else:
        device_type = "Other"

    if os_family == "Android":
        label = "Android Tablet" if device_type == "Tablet" else "Android Mobile"
    elif os_family == "iOS":
        label = "iPhone"
    elif os_family == "iPadOS":
        label = "iPad"
    elif os_family == "Windows":
        label = "Windows PC"
    elif os_family == "macOS":
        label = "Mac"
    elif os_family == "ChromeOS":
        label = "Chromebook"
    elif os_family == "Linux":
        label = "Linux Desktop" if device_type == "Desktop" else "Linux Device"
    else:
        label = f"{os_family} {device_type}".strip()

    browser = parsed.browser.family or "Unknown"
    brands = _client_value(client, "brands", [])
    if isinstance(brands, list):
        brand_names = [str(item.get("brand", "")) for item in brands if isinstance(item, dict)]
        joined = " ".join(brand_names).lower()
        if "microsoft edge" in joined:
            browser = "Edge"
        elif "google chrome" in joined:
            browser = "Chrome"
        elif "chromium" in joined and browser == "Unknown":
            browser = "Chromium"

    model = ch_model or (parsed.device.model or "")
    return (
        device_type,
        label,
        browser,
        os_family,
        model,
        bool(parsed.is_bot),
        device_confidence,
        device_evidence,
    )


def _stable_identity(
    visit: dict[str, Any],
    user_agent: str,
    country: str,
    region: str,
    city: str,
    client: dict[str, Any],
):
    local_storage_id = _safe_text(
        visit.get("local_storage_id") or visit.get("localStorageId") or client.get("localStorageId"),
        128,
    )
    if local_storage_id:
        return f"storage:{local_storage_id}", "Browser storage"

    cookie_id = _safe_text(
        visit.get("cookie_id")
        or visit.get("visitor_id")
        or visit.get("visitorId"),
        128,
    )
    if cookie_id:
        return f"cookie:{cookie_id}", "First-party cookie"

    fingerprint_hash = _safe_text(visit.get("fingerprint_hash"), 128)
    if fingerprint_hash:
        return f"fingerprint:{fingerprint_hash}", "Anonymous fingerprint"

    ip_value = _safe_text(
        visit.get("ip_hash")
        or visit.get("ipHash")
        or visit.get("remoteAddr")
        or visit.get("remote_addr"),
        256,
    )
    if ip_value:
        fallback = f"{ip_value}|{user_agent}|{country}|{region}|{city}"
        return sha256(fallback.encode("utf-8", "ignore")).hexdigest(), "Network + browser"

    fallback = f"{user_agent}|{country}|{region}|{city}"
    return sha256(fallback.encode("utf-8", "ignore")).hexdigest(), "Estimated"




def _meaningful_model(value: str) -> str:
    model = _safe_text(value, 160).strip()
    if model.lower() in {"", "k", "desktop", "other", "unknown", "generic", "linux x86_64"}:
        return ""
    return model


def _device_cluster_identity(
    visit: dict[str, Any],
    *,
    browser_identity: str,
    os_family: str,
    model: str,
    client: dict[str, Any],
) -> tuple[str, str, str, str]:
    """Return an estimated physical-device identity across browser contexts.

    Browser storage is reliable only inside one browser/profile. Messaging apps
    often use an in-app WebView and then open the same link in Chrome, which
    creates two storage IDs on one phone. Version 4.2 therefore builds a
    separate privacy-preserving hardware/network signature that intentionally
    excludes localStorage ID, cookies, browser name and full user-agent.

    The result is an estimate, not a MAC address or hardware serial number.
    """
    supplied = _safe_text(
        visit.get("device_signature_hash")
        or visit.get("deviceSignatureHash")
        or client.get("deviceSignatureHash"),
        128,
    )
    if supplied:
        ip_hash = _safe_text(visit.get("ip_hash") or visit.get("ipHash"), 128)
        stable_model = _meaningful_model(model)
        signature_scope = f"{ip_hash}|{os_family.lower()}|{supplied}"
        confidence = "High" if ip_hash and stable_model else "Medium"
        return (
            "device-signature:" + sha256(signature_scope.encode("utf-8", "ignore")).hexdigest(),
            "Cross-browser device signature",
            confidence,
            "Stable hardware/screen signature combined with the salted network scope",
        )

    def _int(key: str) -> int:
        try:
            return int(float(_client_value(client, key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    def _float(key: str) -> float:
        try:
            return round(float(_client_value(client, key, 0) or 0), 2)
        except (TypeError, ValueError):
            return 0.0

    width = _int("screenWidth")
    height = _int("screenHeight")
    short_edge, long_edge = sorted((width, height)) if width and height else (0, 0)
    touch = _int("maxTouchPoints")
    cores = _int("hardwareConcurrency")
    memory = _float("deviceMemory")
    pixel_ratio = _float("pixelRatio")
    timezone_name = _safe_text(_client_value(client, "timezone"), 100).strip()
    language = _safe_text(_client_value(client, "language"), 40).strip().lower()
    architecture = _safe_text(_client_value(client, "architecture"), 40).strip().lower()
    bitness = _safe_text(_client_value(client, "bitness"), 20).strip().lower()
    ip_hash = _safe_text(visit.get("ip_hash") or visit.get("ipHash"), 128)
    stable_model = _meaningful_model(model)

    hardware_parts = {
        "os": os_family.lower(),
        "model": stable_model.lower(),
        "screen": f"{short_edge}x{long_edge}" if short_edge and long_edge else "",
        "ratio": f"{pixel_ratio:.2f}" if pixel_ratio else "",
        "touch": str(touch) if touch else "",
        "cores": str(cores) if cores else "",
        "memory": f"{memory:.1f}" if memory else "",
        "timezone": timezone_name.lower(),
        "language": language,
        "architecture": architecture,
        "bitness": bitness,
    }
    present_hardware = [value for key, value in hardware_parts.items() if key != "os" and value]

    # IP is salted before storage. Combining it with at least three independent
    # device signals substantially reduces accidental merging on shared Wi-Fi.
    if ip_hash and len(present_hardware) >= 3:
        canonical = "|".join([ip_hash] + [f"{k}={hardware_parts[k]}" for k in sorted(hardware_parts)])
        confidence = "High" if stable_model or len(present_hardware) >= 6 else "Medium"
        evidence = (
            "Estimated across app/browser contexts using salted network, OS, "
            "screen, touch and hardware signals"
        )
        return (
            "estimated-device:" + sha256(canonical.encode("utf-8", "ignore")).hexdigest(),
            "Cross-context estimate",
            confidence,
            evidence,
        )

    # Without enough cross-context evidence, do not merge unrelated people.
    return (
        f"browser-device:{browser_identity}",
        "Browser identity",
        "Browser-only",
        "Not enough hardware evidence to merge this browser with another context",
    )


def _parse_client_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def normalize_visit(visit: dict[str, Any]):
    user_agent = _safe_text(visit.get("userAgent") or visit.get("user_agent"), 2000)
    referrer = _safe_text(visit.get("referer") or visit.get("referrer"), 4000)
    document_referrer = _safe_text(visit.get("document_referrer"), 4000)
    x_requested_with = _safe_text(visit.get("x_requested_with"), 300)
    client = _parse_client_payload(visit.get("client") or visit.get("client_payload"))
    location = visit.get("visitLocation") or visit.get("location") or {}
    if not isinstance(location, dict):
        location = {}
    country = _safe_text(
        visit.get("country")
        or location.get("countryName")
        or location.get("countryCode")
        or "Unknown",
        80,
    )
    region = _safe_text(
        visit.get("region") or location.get("regionName") or location.get("region"), 120
    )
    city = _safe_text(visit.get("city") or location.get("cityName") or location.get("city"), 120)

    explicit_platform = _safe_text(visit.get("platform"), 120)
    if explicit_platform:
        platform = explicit_platform
        surface = _safe_text(visit.get("surface"), 80) or "Browser or app"
        confidence = _safe_text(visit.get("confidence"), 40) or "Hidden"
        evidence = _safe_text(visit.get("evidence"), 500) or "Stored detection result"
    else:
        platform, surface, confidence, evidence = detect_platform(
            referrer,
            user_agent,
            x_requested_with=x_requested_with,
            document_referrer=document_referrer,
        )

    date = _safe_text(visit.get("date") or visit.get("visitedAt") or visit.get("created_at"), 100)
    (
        device, device_label, browser, os_family, model, ua_bot,
        device_confidence, device_evidence,
    ) = _device_details(user_agent, client)
    explicit_device = _safe_text(visit.get("device_label"), 120)
    if explicit_device:
        device_label = explicit_device
    browser = _safe_text(visit.get("browser"), 120) or browser
    os_family = _safe_text(visit.get("os"), 120) or os_family
    model = _safe_text(visit.get("model"), 160) or model
    potential_bot = bool(
        visit.get("potentialBot")
        or visit.get("isBot")
        or visit.get("is_bot")
        or ua_bot
    )
    browser_identity, identity_method = _stable_identity(
        visit, user_agent, country, region, city, client
    )
    browser_identity_id = (
        "B-" + sha256(browser_identity.encode("utf-8", "ignore")).hexdigest()[:10].upper()
    )
    device_identity, device_identity_method, device_identity_confidence, device_identity_evidence = (
        _device_cluster_identity(
            visit,
            browser_identity=browser_identity,
            os_family=os_family,
            model=model,
            client=client,
        )
    )
    public_device_id = (
        "D-" + sha256(device_identity.encode("utf-8", "ignore")).hexdigest()[:10].upper()
    )

    return {
        "date": date,
        "platform": platform,
        "surface": surface,
        "confidence": confidence,
        "evidence": evidence,
        "referrer": document_referrer or referrer,
        "browser": browser,
        "os": os_family,
        "device": device,
        "device_label": device_label,
        "model": model,
        "device_confidence": device_confidence,
        "device_evidence": device_evidence,
        "country": country,
        "region": region,
        "city": city,
        "is_bot": potential_bot,
        "identity": browser_identity,
        "identity_method": identity_method,
        "browser_identity_id": browser_identity_id,
        "device_identity": device_identity,
        "device_identity_method": device_identity_method,
        "device_identity_confidence": device_identity_confidence,
        "device_identity_evidence": device_identity_evidence,
        "device_id": public_device_id,
        "collection_status": _safe_text(visit.get("collection_status"), 32) or "server-only",
        "tracking_version": _safe_text(visit.get("tracking_version"), 16) or "legacy",
    }


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sort_timestamp(value: Any) -> float:
    parsed = _parse_date(value)
    return parsed.timestamp() if parsed else 0.0


def _apply_recent_preview_attribution(
    verified_humans: list[dict[str, Any]],
    preview_rows: list[dict[str, Any]],
) -> None:
    """Attach a conservative probable platform to hidden human clicks.

    WhatsApp and other apps often fetch a preview with an identifiable bot UA,
    then launch external Chrome without referrer/app headers. The requests cannot
    be cryptographically linked. We therefore use only a short preceding window
    and label the result Probable, never Confirmed.
    """
    candidates = [
        row
        for row in preview_rows
        if row["platform"] != "Unknown / Hidden" and _parse_date(row["date"])
    ]
    for row in verified_humans:
        if row["platform"] != "Unknown / Hidden":
            continue
        click_time = _parse_date(row["date"])
        if not click_time:
            continue
        best: tuple[float, dict[str, Any]] | None = None
        for preview in candidates:
            preview_time = _parse_date(preview["date"])
            if not preview_time:
                continue
            delta = (click_time - preview_time).total_seconds()
            if 0 <= delta <= PREVIEW_CORRELATION_WINDOW_SECONDS:
                if best is None or delta < best[0]:
                    best = (delta, preview)
        if best is None:
            continue
        delta, preview = best
        row["platform"] = preview["platform"]
        row["surface"] = "Likely app launch"
        row["confidence"] = "Probable"
        row["evidence"] = (
            f'{preview["platform"]} preview request occurred {int(delta)}s before this browser click; '
            "the launching app removed direct browser evidence"
        )


def aggregate_visits(visits: list[dict[str, Any]]):
    rows = [normalize_visit(v) for v in visits]
    rows.sort(key=lambda row: _sort_timestamp(row["date"]), reverse=True)

    bots = [row for row in rows if row["is_bot"]]
    verified_humans = [
        row
        for row in rows
        if not row["is_bot"] and row["collection_status"] == "enriched"
    ]
    unverified_humans = [
        row
        for row in rows
        if not row["is_bot"] and row["collection_status"] != "enriched"
    ]
    _apply_recent_preview_attribution(verified_humans, bots)
    humans = verified_humans

    counters = {
        "platforms": Counter(v["platform"] for v in humans),
        "surfaces": Counter(v["surface"] for v in humans),
        "devices": Counter(v["device_label"] for v in humans),
        "browsers": Counter(v["browser"] for v in humans),
        "operating_systems": Counter(v["os"] for v in humans),
        "countries": Counter(v["country"] for v in humans),
        "confidence": Counter(v["confidence"] for v in humans),
        "device_confidence": Counter(v["device_confidence"] for v in humans),
        "collection_status": Counter(v["collection_status"] for v in rows),
    }
    daily: defaultdict[str, int] = defaultdict(int)
    for row in humans:
        parsed_date = _parse_date(row["date"])
        day = parsed_date.strftime("%Y-%m-%d") if parsed_date else "Unknown"
        daily[day] += 1

    grouped: dict[str, dict[str, Any]] = {}
    browser_identities = {row["identity"] for row in humans}
    for row in humans:
        bucket = grouped.setdefault(
            row["device_identity"],
            {
                "device_id": row["device_id"],
                "device_label": row["device_label"],
                "device": row["device"],
                "browser": row["browser"],
                "os": row["os"],
                "model": row["model"],
                "device_confidence": row["device_confidence"],
                "device_evidence": row["device_evidence"],
                "country": row["country"],
                "identity_method": row["device_identity_method"],
                "identity_confidence": row["device_identity_confidence"],
                "identity_evidence": row["device_identity_evidence"],
                "clicks": 0,
                "platform_counter": Counter(),
                "confidence_counter": Counter(),
                "browser_identity_counter": Counter(),
                "browser_counter": Counter(),
                "first_seen": row["date"],
                "last_seen": row["date"],
            },
        )
        bucket["clicks"] += 1
        bucket["platform_counter"][f'{row["platform"]} · {row["surface"]}'] += 1
        bucket["confidence_counter"][row["confidence"]] += 1
        bucket["browser_identity_counter"][row["browser_identity_id"]] += 1
        bucket["browser_counter"][row["browser"]] += 1
        # Prefer the strongest/latest non-hidden classification for a device.
        if bucket["device_confidence"] != "Confirmed" and row["device_confidence"] == "Confirmed":
            bucket["device_label"] = row["device_label"]
            bucket["device"] = row["device"]
            bucket["os"] = row["os"]
            bucket["model"] = row["model"]
            bucket["device_confidence"] = row["device_confidence"]
            bucket["device_evidence"] = row["device_evidence"]
        current = _sort_timestamp(row["date"])
        first = _sort_timestamp(bucket["first_seen"])
        last = _sort_timestamp(bucket["last_seen"])
        if current and (not first or current < first):
            bucket["first_seen"] = row["date"]
        if current and current > last:
            bucket["last_seen"] = row["date"]

    device_rows = []
    for bucket in grouped.values():
        platform_breakdown = bucket.pop("platform_counter")
        confidence_breakdown = bucket.pop("confidence_counter")
        browser_identity_breakdown = bucket.pop("browser_identity_counter")
        browser_breakdown = bucket.pop("browser_counter")
        bucket["platforms"] = [
            {"label": label, "clicks": count}
            for label, count in platform_breakdown.most_common()
        ]
        bucket["top_platform"] = (
            platform_breakdown.most_common(1)[0][0]
            if platform_breakdown
            else "Unknown / Hidden"
        )
        bucket["top_confidence"] = (
            confidence_breakdown.most_common(1)[0][0]
            if confidence_breakdown
            else "Hidden"
        )
        bucket["browser_identities"] = len(browser_identity_breakdown)
        bucket["browsers"] = [
            {"label": label, "clicks": count}
            for label, count in browser_breakdown.most_common()
        ]
        device_rows.append(bucket)
    device_rows.sort(key=lambda row: (-row["clicks"], row["device_id"]))

    unique_devices = len(grouped)
    known_platforms = Counter(
        row["platform"] for row in humans if row["platform"] != "Unknown / Hidden"
    )
    top_platform = (
        known_platforms.most_common(1)[0][0]
        if known_platforms
        else ("Unknown / Hidden" if humans else "No data")
    )
    platform_identified = sum(
        count for name, count in counters["platforms"].items() if name != "Unknown / Hidden"
    )
    top_device = counters["devices"].most_common(1)[0][0] if humans else "No data"
    top_country = counters["countries"].most_common(1)[0][0] if humans else "No data"
    app_clicks = sum(
        1 for row in humans if "app" in row["surface"].lower() or row["surface"] == "Likely app launch"
    )
    web_clicks = sum(1 for row in humans if "web" in row["surface"].lower())
    hidden_clicks = sum(1 for row in humans if row["platform"] == "Unknown / Hidden")

    return {
        # Primary numbers are verified browser clicks only. Preview/bot and
        # incomplete requests are visible separately and never pollute devices.
        "total": len(humans),
        "human": len(humans),
        "bots": len(bots),
        "unverified_requests": len(unverified_humans),
        "all_requests": len(rows),
        "unique_devices": unique_devices,
        "estimated_devices": unique_devices,
        "browser_identities": len(browser_identities),
        "estimated_audience": unique_devices,
        "repeat_clicks": max(0, len(humans) - unique_devices),
        "top_platform": top_platform,
        "top_device": top_device,
        "top_country": top_country,
        "app_clicks": app_clicks,
        "web_clicks": web_clicks,
        "hidden_clicks": hidden_clicks,
        "platform_identified": platform_identified,
        "platform_hidden": max(0, len(humans) - platform_identified),
        "platform_identification_rate": round(
            (platform_identified / len(humans) * 100) if humans else 0, 1
        ),
        "platforms": counters["platforms"].most_common(30),
        "surfaces": counters["surfaces"].most_common(20),
        "devices": counters["devices"].most_common(30),
        "browsers": counters["browsers"].most_common(30),
        "operating_systems": counters["operating_systems"].most_common(30),
        "countries": counters["countries"].most_common(30),
        "confidence": counters["confidence"].most_common(10),
        "device_confidence": counters["device_confidence"].most_common(10),
        "collection_status": counters["collection_status"].most_common(10),
        "enriched_clicks": len(humans),
        "server_only_clicks": len(unverified_humans),
        "preview_requests": len(bots),
        "daily": sorted(daily.items()),
        "device_rows": device_rows,
        "recent": humans[:200],
        "unverified_recent": unverified_humans[:100],
        "preview_recent": bots[:100],
        "all_rows": rows,
    }


def visit_summary(short_url_payload: dict[str, Any]):
    summary = short_url_payload.get("visitsSummary") or {}
    total = int(summary.get("total") or 0)
    bots = int(summary.get("bots") or 0)
    humans = int(summary.get("nonBots") or max(0, total - bots))
    return total, humans, bots
