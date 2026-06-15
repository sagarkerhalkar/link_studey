from link_analytics.extensions import db
from link_analytics.models import ClickEvent, GatewayClickEvent, ManagedLink, VisitEvent
from link_analytics.shlink_client import ShlinkError

from .conftest import login
from .test_app import create_link


def _create_gateway_click(client, tag, headers=None):
    return client.get(
        f"/{tag}",
        base_url="https://s.sagarkerhalkar.com",
        headers=headers or {"User-Agent": "Mozilla/5.0"},
        follow_redirects=False,
    )


def test_old_sources_are_excluded_from_primary_analytics(client, app, fake_shlink):
    login(client)
    create_link(client, tag="integrity-boundary")
    with app.app_context():
        link = ManagedLink.query.filter_by(short_code="integrity-boundary").one()
        db.session.add(
            VisitEvent(
                managed_link_id=link.id,
                visitor_id="old-v2",
                user_agent="Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile",
                source_hint="WhatsApp",
            )
        )
        db.session.add(
            ClickEvent(
                click_token="old-v3-token",
                managed_link_id=link.id,
                cookie_id="old-v3",
                platform="WhatsApp",
                surface="Mobile app",
                confidence="Confirmed",
                device_label="Linux Desktop",
                browser="Chrome",
                os_family="Linux",
            )
        )
        db.session.commit()
        link_id = link.id
    fake_shlink.links["integrity-boundary"]["visitsSummary"] = {
        "total": 8,
        "nonBots": 8,
        "bots": 0,
    }
    fake_shlink.visits["integrity-boundary"] = [
        {
            "date": "2026-06-15T00:00:00Z",
            "referer": "https://web.whatsapp.com/",
            "userAgent": "Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile",
        }
    ]

    page = client.get(f"/links/{link_id}/analytics")
    assert page.status_code == 200
    assert b"Historical records are separated" in page.data

    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["tracking_scope"] == "gateway-v4.2-only"
    assert data["total"] == 0
    assert data["devices"] == []
    assert data["platforms"] == []


def test_gateway_click_is_the_only_primary_source(client, app):
    login(client)
    create_link(client, tag="gateway-only")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="gateway-only").one().id

    response = _create_gateway_click(
        client,
        "gateway-only",
        {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/140 Mobile",
            "X-Requested-With": "com.whatsapp",
        },
    )
    assert response.status_code == 200

    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["total"] == 0
    assert data["unverified_requests"] == 1
    assert data["recent"] == []


def test_collector_enrichment_updates_status_and_device(client, app):
    login(client)
    create_link(client, tag="collector-v4")
    _create_gateway_click(
        client,
        "collector-v4",
        {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile"},
    )
    with app.app_context():
        event = GatewayClickEvent.query.one()
        token = event.click_token
        link_id = event.managed_link_id

    response = client.post(
        f"/__track/collect/{token}",
        json={
            "localStorageId": "stable-v4-browser",
            "fingerprintHash": "b" * 64,
            "documentReferrer": "android-app://com.whatsapp/",
            "client": {
                "platform": "Android",
                "mobile": True,
                "model": "Pixel 8",
                "maxTouchPoints": 5,
                "screenWidth": 412,
                "screenHeight": 915,
            },
        },
    )
    assert response.status_code == 200

    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["enriched_clicks"] == 1
    assert data["server_only_clicks"] == 0
    recent = data["recent"][0]
    assert recent["collection_status"] == "enriched"
    assert recent["platform"] == "WhatsApp"
    assert recent["confidence"] == "Confirmed"
    assert recent["device_label"] == "Android Mobile"
    assert recent["model"] == "Pixel 8"


def test_live_endpoint_does_not_depend_on_shlink(client, app, fake_shlink):
    login(client)
    create_link(client, tag="live-no-shlink")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="live-no-shlink").one().id
    _create_gateway_click(client, "live-no-shlink")

    def fail(*_args, **_kwargs):
        raise ShlinkError("offline")

    fake_shlink.get_short_url = fail
    fake_shlink.get_visits = fail
    fake_shlink.list_short_urls = fail

    response = client.get(f"/api/links/{link_id}/analytics/live")
    assert response.status_code == 200
    assert response.get_json()["analytics"]["all_requests"] == 1


def test_export_contains_only_gateway_v4_rows(client, app):
    login(client)
    create_link(client, tag="export-v4")
    _create_gateway_click(client, "export-v4")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="export-v4").one().id
        link = db.session.get(ManagedLink, link_id)
        db.session.add(
            VisitEvent(
                managed_link_id=link.id,
                visitor_id="legacy-export",
                source_hint="Instagram",
            )
        )
        db.session.commit()

    response = client.get(f"/links/{link_id}/export.csv")
    assert response.status_code == 200
    assert b"tracking_version" in response.data
    assert b"4.2" in response.data
    assert b"legacy-export" not in response.data


def test_v4_cookie_is_stable_for_repeat_clicks(client, app):
    login(client)
    create_link(client, tag="repeat-v4")
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile"}
    _create_gateway_click(client, "repeat-v4", headers)
    _create_gateway_click(client, "repeat-v4", headers)
    with app.app_context():
        events = GatewayClickEvent.query.order_by(GatewayClickEvent.id).all()
        assert len(events) == 2
        assert len({event.cookie_id for event in events}) == 1
        link_id = events[0].managed_link_id
        tokens = [event.click_token for event in events]
    for token in tokens:
        response = client.post(
            f"/__track/collect/{token}",
            json={
                "localStorageId": "same-android-browser",
                "client": {
                    "platform": "Android",
                    "mobile": True,
                    "maxTouchPoints": 5,
                    "screenWidth": 412,
                    "screenHeight": 915,
                    "pixelRatio": 2.75,
                },
            },
        )
        assert response.status_code == 200
    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["unique_devices"] == 1
    assert data["repeat_clicks"] == 1
    assert data["device_rows"][0]["clicks"] == 2


def test_v42_merges_same_physical_device_across_browser_contexts(client, app):
    login(client)
    create_link(client, tag="cross-context-v42")
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 16; Pixel 8) Chrome/149 Mobile"}
    _create_gateway_click(client, "cross-context-v42", headers)
    _create_gateway_click(client, "cross-context-v42", headers)
    with app.app_context():
        events = GatewayClickEvent.query.order_by(GatewayClickEvent.id).all()
        link_id = events[0].managed_link_id
        tokens = [event.click_token for event in events]

    common_client = {
        "platform": "Android",
        "mobile": True,
        "model": "Pixel 8",
        "maxTouchPoints": 5,
        "screenWidth": 412,
        "screenHeight": 915,
        "pixelRatio": 2.75,
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "timezone": "Asia/Kolkata",
        "language": "en-IN",
        "deviceSignatureHash": "same-physical-hardware",
    }
    for index, token in enumerate(tokens):
        response = client.post(
            f"/__track/collect/{token}",
            json={
                "localStorageId": f"different-browser-context-{index}",
                "deviceSignatureHash": "same-physical-hardware",
                "client": common_client,
            },
        )
        assert response.status_code == 200

    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["total"] == 2
    assert data["estimated_devices"] == 1
    assert data["browser_identities"] == 2
    assert data["repeat_clicks"] == 1
    assert data["device_rows"][0]["clicks"] == 2
    assert data["device_rows"][0]["browser_identities"] == 2
    assert data["device_rows"][0]["identity_method"] == "Cross-browser device signature"


def test_v42_does_not_merge_different_hardware_on_same_network(client, app):
    login(client)
    create_link(client, tag="different-hardware-v42")
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 16) Chrome/149 Mobile"}
    _create_gateway_click(client, "different-hardware-v42", headers)
    _create_gateway_click(client, "different-hardware-v42", headers)
    with app.app_context():
        events = GatewayClickEvent.query.order_by(GatewayClickEvent.id).all()
        link_id = events[0].managed_link_id
        tokens = [event.click_token for event in events]

    for index, token in enumerate(tokens):
        response = client.post(
            f"/__track/collect/{token}",
            json={
                "localStorageId": f"device-{index}",
                "deviceSignatureHash": f"hardware-{index}",
                "client": {
                    "platform": "Android",
                    "mobile": True,
                    "model": f"Phone {index}",
                    "maxTouchPoints": 5,
                    "screenWidth": 412 + index,
                    "screenHeight": 915 + index,
                    "pixelRatio": 2.75,
                    "deviceSignatureHash": f"hardware-{index}",
                },
            },
        )
        assert response.status_code == 200

    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["estimated_devices"] == 2
    assert data["browser_identities"] == 2
    assert data["repeat_clicks"] == 0


def test_v42_global_analytics_view_is_present(client, app):
    login(client)
    create_link(client, tag="global-view-v42")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="global-view-v42").one().id
    page = client.get(f"/links/{link_id}/analytics")
    assert page.status_code == 200
    assert b"Global traffic intelligence" in page.data
    assert b"From request to real audience" in page.data
    assert b"One device, all its clicks and platforms" in page.data
    assert b"data-live-device-cards" in page.data
    assert b"Gateway v4.2" in page.data


def test_v42_merges_existing_v41_rows_using_hardware_fallback(client, app):
    login(client)
    create_link(client, tag="v41-hardware-fallback")
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/149"}
    _create_gateway_click(client, "v41-hardware-fallback", headers)
    _create_gateway_click(client, "v41-hardware-fallback", headers)
    with app.app_context():
        events = GatewayClickEvent.query.order_by(GatewayClickEvent.id).all()
        link_id = events[0].managed_link_id
        tokens = [event.click_token for event in events]

    common_client = {
        "platform": "Linux",
        "mobile": False,
        "model": "",
        "maxTouchPoints": 5,
        "screenWidth": 413,
        "screenHeight": 919,
        "pixelRatio": 2.625,
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "timezone": "Asia/Kolkata",
        "language": "en-IN",
    }
    for index, token in enumerate(tokens):
        response = client.post(
            f"/__track/collect/{token}",
            json={
                "localStorageId": f"old-context-{index}",
                "client": common_client,
            },
        )
        assert response.status_code == 200

    data = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert data["estimated_devices"] == 1
    assert data["browser_identities"] == 2
    assert data["device_rows"][0]["device_label"] == "Android Mobile"
    assert data["device_rows"][0]["identity_method"] == "Cross-context estimate"
