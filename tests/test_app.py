from link_analytics.analytics import aggregate_visits, detect_source
from link_analytics.extensions import db
from link_analytics.models import GatewayClickEvent, ManagedLink, User

from .conftest import login


def create_link(client, tag="8hb2kld", destination="https://example.com/long/path"):
    return client.post(
        "/links/new",
        data={"destination_url": destination, "custom_tag": tag},
        follow_redirects=True,
    )


def test_public_pages_and_security_headers(client):
    for path in ["/", "/login", "/privacy", "/terms", "/healthz"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert b"https://s.sagarkerhalkar.com/your-tag" in client.get("/").data


def test_login_and_logout(client):
    response = login(client)
    assert response.status_code == 200
    assert b"Link performance at a glance" in response.data
    response = client.post("/logout", follow_redirects=True)
    assert b"Short branded links" in response.data


def test_invalid_login(client):
    response = client.post(
        "/login", data={"username": "admin", "password": "wrong"}, follow_redirects=True
    )
    assert b"Incorrect username or password" in response.data


def test_create_link_uses_exact_tag(client, fake_shlink, app):
    login(client)
    response = create_link(client)
    assert response.status_code == 200
    assert b"https://s.sagarkerhalkar.com/8hb2kld" in response.data
    assert "8hb2kld" in fake_shlink.links
    with app.app_context():
        link = ManagedLink.query.one()
        assert link.short_code == "8hb2kld"
        assert link.short_url == "https://s.sagarkerhalkar.com/8hb2kld"


def test_duplicate_tag_is_rejected(client):
    login(client)
    create_link(client)
    response = create_link(client)
    assert b"This tag is already in use" in response.data


def test_tag_validation(client):
    login(client)
    response = create_link(client, tag="bad tag")
    assert b"letters, numbers, hyphens, or underscores" in response.data
    response = create_link(client, tag="api")
    assert b"reserved" in response.data


def test_edit_destination_does_not_change_short_link(client, fake_shlink, app):
    login(client)
    create_link(client)
    with app.app_context():
        link_id = ManagedLink.query.one().id
    response = client.post(
        f"/links/{link_id}/edit",
        data={"destination_url": "https://example.org/updated"},
        follow_redirects=True,
    )
    assert b"Destination updated" in response.data
    assert fake_shlink.links["8hb2kld"]["longUrl"] == "https://example.org/updated"
    assert b"https://s.sagarkerhalkar.com/8hb2kld" in response.data


def test_analytics_source_device_and_export(client, fake_shlink, app):
    login(client)
    create_link(client)
    fake_shlink.visits["8hb2kld"] = [
        {
            "date": "2026-06-14T08:30:00+00:00",
            "referer": "https://web.whatsapp.com/",
            "userAgent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/140 Mobile",
            "visitLocation": {"countryName": "India", "regionName": "Madhya Pradesh", "cityName": "Bhopal"},
            "potentialBot": False,
        },
        {
            "date": "2026-06-14T09:30:00+00:00",
            "referer": "",
            "userAgent": "Instagram 330.0 Android",
            "visitLocation": {"countryName": "India"},
            "potentialBot": False,
        },
        {
            "date": "2026-06-14T10:30:00+00:00",
            "referer": "",
            "userAgent": "Googlebot/2.1",
            "visitLocation": {},
            "potentialBot": True,
        },
    ]
    fake_shlink.links["8hb2kld"]["visitsSummary"] = {"total": 3, "nonBots": 2, "bots": 1}
    with app.app_context():
        link_id = ManagedLink.query.one().id
    response = client.get(f"/links/{link_id}/analytics")
    assert response.status_code == 200
    assert b"Historical records are separated" in response.data
    assert b"Gateway v4.2" in response.data
    live = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert live["total"] == 0
    assert live["platforms"] == []
    export = client.get(f"/links/{link_id}/export.csv")
    assert export.status_code == 200
    assert export.mimetype == "text/csv"
    assert b"tracking_version" in export.data
    assert b"WhatsApp" not in export.data


def test_qr_download(client, app):
    login(client)
    create_link(client)
    with app.app_context():
        link_id = ManagedLink.query.one().id
    response = client.get(f"/links/{link_id}/qr.png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"


def test_delete_removes_remote_and_local(client, fake_shlink, app):
    login(client)
    create_link(client)
    with app.app_context():
        link_id = ManagedLink.query.one().id
    response = client.post(f"/links/{link_id}/delete", follow_redirects=True)
    assert b"Short link deleted" in response.data
    assert "8hb2kld" not in fake_shlink.links
    with app.app_context():
        assert ManagedLink.query.count() == 0


def test_viewer_cannot_create_or_delete(client, app):
    login(client, "viewer", "ViewerPassword123!")
    assert client.get("/links/new").status_code == 403
    with app.app_context():
        owner = User.query.filter_by(username="viewer").one()
        link = ManagedLink(
            owner_id=owner.id,
            short_code="viewtag",
            custom_tag="viewtag",
            long_url="https://example.com",
            short_url="https://s.sagarkerhalkar.com/viewtag",
            domain="s.sagarkerhalkar.com",
        )
        db.session.add(link)
        db.session.commit()
        link_id = link.id
    assert client.post(f"/links/{link_id}/delete").status_code == 403


def test_admin_user_management_and_password_change(client, app):
    login(client)
    response = client.post(
        "/users/new",
        data={
            "display_name": "New User",
            "username": "newuser",
            "email": "new@example.com",
            "role": "analyst",
            "password": "LongPassword123!",
            "must_change_password": "y",
            "is_active": "y",
        },
        follow_redirects=True,
    )
    assert b"User created" in response.data
    with app.app_context():
        user = User.query.filter_by(username="newuser").one()
        assert user.role == "analyst"

    response = client.post(
        "/settings/password",
        data={
            "current_password": "AdminPassword123!",
            "new_password": "NewAdminPassword123!",
            "confirm_password": "NewAdminPassword123!",
        },
        follow_redirects=True,
    )
    assert b"Password changed successfully" in response.data


def test_theme_assets_and_form_are_correct(client):
    login(client)
    form = client.get("/links/new")
    assert b"Destination URL" in form.data
    assert b"My tag" in form.data
    assert b"Custom alias" not in form.data
    assert b"share tag" not in form.data.lower()
    script = client.get("/static/js/app.js")
    assert b"localStorage.setItem('la-theme'" in script.data
    css = client.get("/static/css/app.css")
    assert b'html[data-theme="light"]' in css.data
    assert b"--font-ui" in css.data


def test_source_detection_truthfulness():
    assert detect_source("https://web.whatsapp.com/", "")[0] == "WhatsApp"
    assert detect_source("", "Instagram Android")[0] == "Instagram"
    assert detect_source("", "Mozilla/5.0")[0] == "Unknown / Hidden"
    data = aggregate_visits(
        [
            {"date": "2026-06-14T00:00:00Z", "referer": "", "userAgent": "Mozilla/5.0", "potentialBot": False, "collection_status": "enriched"},
            {"date": "2026-06-14T01:00:00Z", "referer": "", "userAgent": "Mozilla/5.0", "potentialBot": False, "collection_status": "enriched"},
        ]
    )
    assert data["total"] == 2
    assert data["estimated_audience"] == 1
    assert data["repeat_clicks"] == 1


def test_ready_and_integration_status(client):
    ready = client.get("/readyz")
    assert ready.status_code == 200
    login(client)
    response = client.get("/settings/integration")
    assert response.status_code == 200
    assert b"Connected" in response.data
    assert b"s.sagarkerhalkar.com" in response.data


def test_wrong_current_password(client):
    login(client)
    response = client.post(
        "/settings/password",
        data={
            "current_password": "not-correct",
            "new_password": "NewAdminPassword123!",
            "confirm_password": "NewAdminPassword123!",
        },
        follow_redirects=True,
    )
    assert b"Current password is incorrect" in response.data


def test_admin_edit_and_reset_user_password(client, app):
    login(client)
    with app.app_context():
        user = User.query.filter_by(username="analyst").one()
        user_id = user.id
    response = client.post(
        f"/users/{user_id}/edit",
        data={
            "display_name": "Analytics Manager",
            "username": "analyst",
            "email": "analytics@example.com",
            "role": "analyst",
            "must_change_password": "y",
            "is_active": "y",
        },
        follow_redirects=True,
    )
    assert b"User updated" in response.data
    response = client.post(
        f"/users/{user_id}/reset-password",
        data={
            "new_password": "ResetPassword123!",
            "confirm_password": "ResetPassword123!",
            "require_change": "y",
        },
        follow_redirects=True,
    )
    assert b"Password reset" in response.data
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.display_name == "Analytics Manager"
        assert user.check_password("ResetPassword123!")


def test_non_admin_cannot_manage_users(client):
    login(client, "analyst", "AnalystPassword123!")
    assert client.get("/users").status_code == 403
    assert client.get("/users/new").status_code == 403


def test_admin_cli_status(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["has-admin"])
    assert result.exit_code == 0
    assert "Administrator exists" in result.output


def test_tracking_gateway_same_url_android_device_repeat_clicks_and_live_api(client, app):
    from link_analytics.models import GatewayClickEvent

    login(client)
    create_link(client, tag="android-test")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="android-test").one().id

    android_ua = (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
        "AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36"
    )
    headers = {
        "User-Agent": android_ua,
        "CF-Connecting-IP": "203.0.113.10",
        "X-Requested-With": "com.whatsapp",
    }
    first = client.get(
        "/android-test",
        base_url="https://s.sagarkerhalkar.com",
        headers=headers,
        follow_redirects=False,
    )
    second = client.get(
        "/android-test",
        base_url="https://s.sagarkerhalkar.com",
        headers=headers,
        follow_redirects=False,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert b"Opening secure link" in first.data
    assert b"?src=" not in first.data

    with app.app_context():
        events = GatewayClickEvent.query.filter_by(managed_link_id=link_id).order_by(GatewayClickEvent.id).all()
        assert len(events) == 2
        assert len({event.cookie_id for event in events}) == 1
        tokens = [event.click_token for event in events]

    client_payload = {
        "localStorageId": "same-android-browser",
        "fingerprintHash": "a" * 64,
        "documentReferrer": "",
        "client": {
            "platform": "Android",
            "mobile": True,
            "model": "Pixel 8 Pro",
            "maxTouchPoints": 5,
            "screenWidth": 412,
            "screenHeight": 915,
        },
    }
    for token in tokens:
        response = client.post(f"/__track/collect/{token}", json=client_payload)
        assert response.status_code == 200

    live = client.get(f"/api/links/{link_id}/analytics/live")
    assert live.status_code == 200
    analytics = live.get_json()["analytics"]
    assert analytics["unique_devices"] == 1
    assert analytics["repeat_clicks"] == 1
    assert analytics["device_rows"][0]["device_label"] == "Android Mobile"
    assert analytics["device_rows"][0]["os"] == "Android"
    assert analytics["device_rows"][0]["model"] == "Pixel 8 Pro"
    assert analytics["device_rows"][0]["clicks"] == 2
    assert analytics["device_rows"][0]["top_platform"] == "WhatsApp · Mobile app"
    assert analytics["recent"][0]["confidence"] == "Confirmed"
    assert "Android app package" in analytics["recent"][0]["evidence"]


def test_generic_android_click_does_not_invent_platform(client, app):
    login(client)
    create_link(client, tag="generic-android")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="generic-android").one().id

    response = client.get(
        "/generic-android",
        base_url="https://s.sagarkerhalkar.com",
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/140 Mobile",
            "CF-Connecting-IP": "203.0.113.11",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    with app.app_context():
        token = GatewayClickEvent.query.filter_by(managed_link_id=link_id).one().click_token
    collected = client.post(
        f"/__track/collect/{token}",
        json={
            "localStorageId": "generic-android-browser",
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
    assert collected.status_code == 200
    analytics = client.get(f"/api/links/{link_id}/analytics/live").get_json()["analytics"]
    assert analytics["recent"][0]["platform"] == "Unknown / Hidden"
    assert analytics["recent"][0]["device_label"] == "Android Mobile"
    assert analytics["recent"][0]["os"] == "Android"
    assert analytics["recent"][0]["confidence"] == "Hidden"


def test_mixed_invalid_dates_do_not_break_analytics_page(client, fake_shlink, app):
    login(client)
    create_link(client, tag="mixed-dates")
    fake_shlink.visits["mixed-dates"] = [
        {"date": "", "userAgent": "Mozilla/5.0", "referer": ""},
        {"date": "2026-06-15T10:00:00+00:00", "userAgent": "Mozilla/5.0", "referer": ""},
    ]
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="mixed-dates").one().id
    page = client.get(f"/links/{link_id}/analytics")
    assert page.status_code == 200
    assert b"Evidence behind every result" in page.data
    live = client.get(f"/api/links/{link_id}/analytics/live")
    assert live.status_code == 200


def test_dashboard_live_endpoint_updates_counts(client, app):
    login(client)
    create_link(client, tag="live-dashboard")
    client.get(
        "/live-dashboard",
        base_url="https://s.sagarkerhalkar.com",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140"},
        follow_redirects=False,
    )
    with app.app_context():
        token = GatewayClickEvent.query.one().click_token
    client.post(
        f"/__track/collect/{token}",
        json={
            "localStorageId": "live-dashboard-device",
            "client": {"platform": "Windows", "mobile": False},
        },
    )
    payload = client.get("/api/dashboard/live").get_json()
    assert payload["total_clicks"] == 1
    assert payload["human_clicks"] == 1
    assert payload["links"][0]["clicks"] == 1


def test_short_link_head_redirect_does_not_create_click(client, app):
    from link_analytics.models import GatewayClickEvent

    login(client)
    create_link(client, tag="head-check")
    response = client.head(
        "/head-check",
        base_url="https://s.sagarkerhalkar.com",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "https://example.com/long/path"
    with app.app_context():
        assert GatewayClickEvent.query.count() == 0


def test_create_admin_env_cli(tmp_path, fake_shlink, monkeypatch):
    from link_analytics import create_app
    from link_analytics.models import User

    database = tmp_path / "cli-admin.db"
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "cli-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database.as_posix()}",
            "AUTO_CREATE_DB": True,
            "SHLINK_CLIENT_FACTORY": lambda: fake_shlink,
            "TRUST_PROXY": False,
        }
    )
    monkeypatch.setenv("LA_ADMIN_USERNAME", "sagar")
    monkeypatch.setenv("LA_ADMIN_DISPLAY_NAME", "Sagar Kerhalkar")
    monkeypatch.setenv("LA_ADMIN_PASSWORD", "StrongPassword123!")
    result = app.test_cli_runner().invoke(args=["create-admin-env"])
    assert result.exit_code == 0
    assert "Administrator 'sagar' created" in result.output
    with app.app_context():
        user = User.query.filter_by(username="sagar").one()
        assert user.check_password("StrongPassword123!")
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_live_ui_uses_background_fetch_without_page_reload(client, app):
    login(client)
    create_link(client, tag="live-ui")
    with app.app_context():
        link_id = ManagedLink.query.filter_by(short_code="live-ui").one().id
    page = client.get(f"/links/{link_id}/analytics")
    assert b"data-live-analytics" in page.data
    assert b"One unchanged short URL" in page.data
    assert b"Copy tagged link" not in page.data
    assert b"?src=" not in page.data
    script = client.get("/static/js/app.js").data
    assert b"fetch(" in script
    assert b"location.reload" not in script
    assert b"Live update reconnecting" in script
