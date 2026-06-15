import csv
import io
import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

import click
import qrcode
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from werkzeug.middleware.proxy_fix import ProxyFix

from .analytics import aggregate_visits, detect_platform, normalize_visit, visit_summary
from .config import Config
from .extensions import csrf, db, limiter, login_manager
from .forms import CreateLinkForm, EditLinkForm, LoginForm, PasswordForm, ResetPasswordForm, UserForm
from .models import AuditLog, ClickEvent, GatewayClickEvent, ManagedLink, User, VisitEvent
from .shlink_client import ShlinkClient, ShlinkConflict, ShlinkError


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    client_factory = app.config.get("SHLINK_CLIENT_FACTORY")

    def shlink():
        if client_factory:
            return client_factory()
        return ShlinkClient(
            base_url=app.config["SHLINK_API_URL"],
            api_key=app.config["SHLINK_API_KEY"],
            domain=app.config["SHLINK_DOMAIN"],
            timeout=app.config["SHLINK_TIMEOUT_SECONDS"],
            verify_tls=app.config["SHLINK_VERIFY_TLS"],
        )

    def audit(action, entity_type=None, entity_id=None, details=None):
        db.session.add(
            AuditLog(
                actor_id=current_user.id if current_user.is_authenticated else None,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                details=json.dumps(details, default=str) if details else None,
            )
        )

    def accessible_links():
        query = ManagedLink.query
        if not current_user.is_admin:
            query = query.filter_by(owner_id=current_user.id)
        return query

    def get_link(link_id):
        link = db.session.get(ManagedLink, link_id)
        if not link:
            abort(404)
        if not current_user.is_admin and link.owner_id != current_user.id:
            abort(403)
        return link

    def _gateway_event_dicts(link):
        events = (
            GatewayClickEvent.query.filter_by(managed_link_id=link.id)
            .order_by(GatewayClickEvent.created_at.desc())
            .limit(100000)
            .all()
        )
        return [event.as_analytics_dict() for event in events]

    def _legacy_summary(link, fetch_remote=True):
        """Return old counters without mixing them into current analytics.

        Shlink, VisitEvent and the 3.x experiment can contain incomplete or
        differently classified rows. They are retained for audit/history only.
        """
        remote_total = remote_humans = remote_bots = 0
        remote_rows = 0
        error = None
        if fetch_remote:
            try:
                remote = shlink().get_short_url(link.short_code) or {}
                remote_total, remote_humans, remote_bots = visit_summary(remote)
                remote_rows = len(shlink().get_visits(link.short_code))
            except ShlinkError as exc:
                error = str(exc)
        local_v2 = VisitEvent.query.filter_by(managed_link_id=link.id).count()
        local_v3 = ClickEvent.query.filter_by(managed_link_id=link.id).count()
        return {
            "shlink_total": remote_total,
            "shlink_humans": remote_humans,
            "shlink_bots": remote_bots,
            "shlink_rows_returned": remote_rows,
            "local_v2_events": local_v2,
            "local_v3_events": local_v3,
            "total_historical_records": remote_total + local_v2 + local_v3,
            "excluded_from_current_analytics": True,
        }, error

    def _build_link_analytics(link, include_rows=False, include_legacy=True):
        # Primary analytics are exclusively version-4 gateway events. This is
        # the central correctness rule: old Shlink rows and earlier experiments
        # never affect current platform/device charts.
        analytics = aggregate_visits(_gateway_event_dicts(link))
        if include_legacy:
            legacy, error = _legacy_summary(link, fetch_remote=True)
        else:
            legacy, error = _legacy_summary(link, fetch_remote=False)
        analytics["legacy"] = legacy
        analytics["tracking_scope"] = "gateway-v4.2-only"
        if not include_rows:
            analytics.pop("all_rows", None)
        return analytics, error

    def _public_host_is_short_domain():
        host = request.host.split(":", 1)[0].lower().rstrip(".")
        return host == app.config["SHLINK_DOMAIN"].lower().rstrip(".")

    def _client_ip_hash():
        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            or request.remote_addr
            or ""
        )
        if not client_ip:
            return ""
        return sha256(
            f'{app.config["SECRET_KEY"]}|{client_ip}'.encode("utf-8", "ignore")
        ).hexdigest()

    def _request_signals(cookie_id):
        return {
            "user_agent": request.headers.get("User-Agent", "")[:2000],
            "referrer": request.headers.get("Referer", "")[:4000],
            "x_requested_with": request.headers.get("X-Requested-With", "")[:300],
            "cookie_id": cookie_id,
            "ip_hash": _client_ip_hash(),
            "country": request.headers.get("CF-IPCountry", "Unknown")[:80],
            "region": request.headers.get("CF-Region", "")[:120],
            "city": request.headers.get("CF-IPCity", "")[:120],
            "client": {
                "brands": [],
                "platform": request.headers.get("Sec-CH-UA-Platform", "").strip('"')[:120],
                "mobile": request.headers.get("Sec-CH-UA-Mobile", "").strip() == "?1",
                "model": request.headers.get("Sec-CH-UA-Model", "").strip('"')[:160],
            },
        }

    def _apply_detection(event, payload=None):
        payload = payload or {}
        client = payload.get("client") if isinstance(payload.get("client"), dict) else {}
        referrer = payload.get("documentReferrer") or event.document_referrer or event.request_referrer
        platform, surface, confidence, evidence = detect_platform(
            event.request_referrer,
            event.user_agent,
            x_requested_with=event.x_requested_with,
            document_referrer=referrer,
        )
        normalized = normalize_visit(
            {
                "user_agent": event.user_agent,
                "referrer": event.request_referrer,
                "document_referrer": referrer,
                "x_requested_with": event.x_requested_with,
                "cookie_id": event.cookie_id,
                "local_storage_id": payload.get("localStorageId") or event.local_storage_id,
                "fingerprint_hash": payload.get("fingerprintHash") or event.fingerprint_hash,
                "ip_hash": event.ip_hash,
                "country": event.country,
                "region": event.region,
                "city": event.city,
                "platform": platform,
                "surface": surface,
                "confidence": confidence,
                "evidence": evidence,
                "client": client,
                "is_bot": event.is_bot,
            }
        )
        event.platform = platform
        event.surface = surface
        event.confidence = confidence
        event.evidence = evidence
        event.document_referrer = str(referrer or "")[:4000] or None
        event.local_storage_id = str(payload.get("localStorageId") or "")[:128] or event.local_storage_id
        event.fingerprint_hash = str(payload.get("fingerprintHash") or "")[:64] or event.fingerprint_hash
        event.client_payload = json.dumps(client, separators=(",", ":"), ensure_ascii=False)[:12000]
        event.device_label = normalized["device_label"]
        event.browser = normalized["browser"]
        event.os_family = normalized["os"]
        event.model = normalized["model"] or None
        event.is_bot = normalized["is_bot"]
        return normalized

    def _tracking_response(link):
        cookie_id = request.cookies.get("la_device_v4") or uuid4().hex
        new_cookie = "la_device_v4" not in request.cookies
        signals = _request_signals(cookie_id)
        normalized = normalize_visit(signals)
        click_token = uuid4().hex
        event = GatewayClickEvent(
            click_token=click_token,
            managed_link_id=link.id,
            cookie_id=cookie_id,
            ip_hash=signals["ip_hash"] or None,
            request_host=request.host.split(":", 1)[0].lower()[:255],
            request_referrer=signals["referrer"] or None,
            user_agent=signals["user_agent"] or None,
            x_requested_with=signals["x_requested_with"] or None,
            sec_ch_ua=request.headers.get("Sec-CH-UA", "")[:1000] or None,
            sec_ch_platform=request.headers.get("Sec-CH-UA-Platform", "")[:120] or None,
            sec_ch_mobile=request.headers.get("Sec-CH-UA-Mobile", "")[:20] or None,
            sec_ch_model=request.headers.get("Sec-CH-UA-Model", "")[:160] or None,
            sec_fetch_site=request.headers.get("Sec-Fetch-Site", "")[:40] or None,
            sec_fetch_mode=request.headers.get("Sec-Fetch-Mode", "")[:40] or None,
            country=signals["country"] or "Unknown",
            region=signals["region"] or None,
            city=signals["city"] or None,
            platform=normalized["platform"],
            surface=normalized["surface"],
            confidence=normalized["confidence"],
            evidence=normalized["evidence"],
            device_label=normalized["device_label"],
            browser=normalized["browser"],
            os_family=normalized["os"],
            model=normalized["model"] or None,
            is_bot=normalized["is_bot"],
            collection_status="server-only",
        )
        db.session.add(event)
        db.session.commit()

        # Bots and command-line clients are redirected immediately. Human
        # browsers receive a sub-second first-party collector page that enriches
        # this same event, then redirects. It never creates a second click.
        if event.is_bot or not event.user_agent:
            response = redirect(link.long_url, code=302)
        else:
            response = app.make_response(
                render_template(
                    "public/track.html",
                    destination=link.long_url,
                    click_token=click_token,
                )
            )
        if new_cookie:
            response.set_cookie(
                "la_device_v4",
                cookie_id,
                max_age=60 * 60 * 24 * 730,
                secure=request.is_secure,
                httponly=True,
                samesite="Lax",
            )
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Accept-CH"] = (
            "Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform, "
            "Sec-CH-UA-Model, Sec-CH-UA-Full-Version-List"
        )
        return response

    @app.context_processor
    def global_context():
        return {
            "app_name": app.config["APP_NAME"],
            "short_domain": app.config["SHLINK_DOMAIN"],
            "public_short_base_url": app.config["PUBLIC_SHORT_BASE_URL"],
            "current_year": datetime.now(timezone.utc).year,
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.get("/")
    def home():
        return render_template("public/home.html")

    @app.get("/privacy")
    def privacy():
        return render_template("public/privacy.html")

    @app.get("/terms")
    def terms():
        return render_template("public/terms.html")

    @app.get("/healthz")
    @limiter.exempt
    def healthz():
        return jsonify(status="ok", service=app.config["APP_NAME"])

    @app.get("/readyz")
    @limiter.exempt
    def readyz():
        db.session.execute(db.text("SELECT 1"))
        try:
            shlink().health()
        except ShlinkError as exc:
            return jsonify(status="degraded", dashboard="ready", shlink=str(exc)), 503
        return jsonify(status="ready", dashboard="ready", shlink="ready")

    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data.strip().lower()).first()
            if user and user.is_active and user.check_password(form.password.data):
                user.last_login_at = datetime.now(timezone.utc)
                login_user(user, remember=form.remember.data)
                audit("auth.login", "user", user.id)
                db.session.commit()
                return redirect(url_for("change_password") if user.must_change_password else url_for("dashboard"))
            flash("Incorrect username or password.", "danger")
        return render_template("auth/login.html", form=form)

    @app.post("/logout")
    def logout():
        if current_user.is_authenticated:
            audit("auth.logout", "user", current_user.id)
            db.session.commit()
        logout_user()
        return redirect(url_for("home"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        local_links = accessible_links().order_by(ManagedLink.created_at.desc()).all()
        total_clicks = human_clicks = bot_clicks = legacy_clicks = 0
        link_cards = []
        shlink_error = None
        for link in local_links:
            analytics, error = _build_link_analytics(link, include_legacy=True)
            if error and not shlink_error:
                shlink_error = error
            total_clicks += analytics["total"]
            human_clicks += analytics["human"]
            bot_clicks += analytics["bots"]
            legacy_clicks += analytics["legacy"]["total_historical_records"]
            link_cards.append(
                {
                    "link": link,
                    "clicks": analytics["total"],
                    "humans": analytics["human"],
                    "bots": analytics["bots"],
                    "legacy": analytics["legacy"]["total_historical_records"],
                }
            )
        return render_template(
            "dashboard/index.html",
            active_page="dashboard",
            link_cards=link_cards[:8],
            total_links=len(local_links),
            total_clicks=total_clicks,
            human_clicks=human_clicks,
            bot_clicks=bot_clicks,
            legacy_clicks=legacy_clicks,
            shlink_error=shlink_error,
        )

    @app.get("/api/dashboard/live")
    @login_required
    @limiter.limit("180 per minute")
    def dashboard_live():
        local_links = accessible_links().order_by(ManagedLink.created_at.desc()).all()
        total_clicks = human_clicks = bot_clicks = 0
        cards = []
        for link in local_links:
            analytics, _error = _build_link_analytics(link, include_legacy=False)
            total_clicks += analytics["total"]
            human_clicks += analytics["human"]
            bot_clicks += analytics["bots"]
            cards.append(
                {
                    "id": link.id,
                    "clicks": analytics["total"],
                    "humans": analytics["human"],
                    "bots": analytics["bots"],
                }
            )
        return jsonify(
            total_links=len(local_links),
            total_clicks=total_clicks,
            human_clicks=human_clicks,
            bot_clicks=bot_clicks,
            links=cards,
            tracking_scope="gateway-v4.2-only",
        )

    @app.get("/links")
    @login_required
    def links():
        term = request.args.get("q", "").strip()
        query = accessible_links()
        if term:
            like = f"%{term}%"
            query = query.filter(
                db.or_(ManagedLink.custom_tag.ilike(like), ManagedLink.long_url.ilike(like))
            )
        rows = query.order_by(ManagedLink.created_at.desc()).all()
        results = []
        shlink_error = None
        for link in rows:
            analytics, error = _build_link_analytics(link, include_legacy=True)
            if error and not shlink_error:
                shlink_error = error
            results.append(
                {
                    "link": link,
                    "clicks": analytics["total"],
                    "humans": analytics["human"],
                    "bots": analytics["bots"],
                    "legacy": analytics["legacy"]["total_historical_records"],
                }
            )
        return render_template(
            "dashboard/links.html",
            active_page="links",
            results=results,
            search=term,
            shlink_error=shlink_error,
        )

    @app.route("/links/new", methods=["GET", "POST"])
    @login_required
    def create_link():
        if not current_user.can_edit:
            abort(403)
        form = CreateLinkForm()
        if form.validate_on_submit():
            destination = form.destination_url.data.strip()
            tag = form.custom_tag.data.strip()
            try:
                payload = shlink().create_short_url(destination, tag)
            except ShlinkConflict:
                form.custom_tag.errors.append("This tag is already in use. Enter another tag.")
            except ShlinkError as exc:
                flash(f"The shortening engine could not create the link: {exc}", "danger")
            else:
                short_code = payload.get("shortCode") or tag
                short_url = payload.get("shortUrl") or f"{app.config['PUBLIC_SHORT_BASE_URL']}/{short_code}"
                link = ManagedLink(
                    owner_id=current_user.id,
                    short_code=short_code,
                    custom_tag=tag,
                    long_url=payload.get("longUrl") or destination,
                    short_url=short_url,
                    domain=payload.get("domain") or app.config["SHLINK_DOMAIN"],
                )
                db.session.add(link)
                db.session.flush()
                audit("link.create", "managed_link", link.id, {"tag": tag})
                db.session.commit()
                flash("Short link created successfully.", "success")
                return redirect(url_for("link_analytics", link_id=link.id))
        return render_template("dashboard/link_form.html", form=form, active_page="links")

    @app.route("/links/<int:link_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_link(link_id):
        if not current_user.can_edit:
            abort(403)
        link = get_link(link_id)
        form = EditLinkForm(destination_url=link.long_url)
        if form.validate_on_submit():
            destination = form.destination_url.data.strip()
            try:
                payload = shlink().update_short_url(link.short_code, destination)
            except ShlinkError as exc:
                flash(f"The shortening engine could not update the link: {exc}", "danger")
            else:
                link.long_url = payload.get("longUrl") or destination
                audit("link.update", "managed_link", link.id)
                db.session.commit()
                flash("Destination updated. Your short link has not changed.", "success")
                return redirect(url_for("link_analytics", link_id=link.id))
        return render_template("dashboard/link_edit.html", form=form, link=link, active_page="links")

    @app.post("/links/<int:link_id>/delete")
    @login_required
    def delete_link(link_id):
        if not current_user.can_edit:
            abort(403)
        link = get_link(link_id)
        try:
            shlink().delete_short_url(link.short_code)
        except ShlinkError as exc:
            flash(f"The shortening engine could not delete the link: {exc}", "danger")
            return redirect(url_for("link_analytics", link_id=link.id))
        audit("link.delete", "managed_link", link.id, {"tag": link.custom_tag})
        db.session.delete(link)
        db.session.commit()
        flash("Short link deleted.", "success")
        return redirect(url_for("links"))

    @app.get("/links/<int:link_id>/analytics")
    @login_required
    def link_analytics(link_id):
        link = get_link(link_id)
        analytics, error = _build_link_analytics(link)
        return render_template(
            "dashboard/link_analytics.html",
            active_page="links",
            link=link,
            analytics=analytics,
            error=error,
        )

    @app.get("/api/links/<int:link_id>/analytics/live")
    @login_required
    @limiter.limit("180 per minute")
    def link_analytics_live(link_id):
        link = get_link(link_id)
        analytics, error = _build_link_analytics(link, include_legacy=False)
        return jsonify(analytics=analytics, error=error)

    @app.get("/links/<int:link_id>/qr.png")
    @login_required
    def link_qr(link_id):
        link = get_link(link_id)
        image = qrcode.make(link.short_url)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        stream.seek(0)
        return send_file(stream, mimetype="image/png", download_name=f"{link.custom_tag}-qr.png")

    @app.get("/links/<int:link_id>/export.csv")
    @login_required
    def export_link(link_id):
        link = get_link(link_id)
        rows = aggregate_visits(_gateway_event_dicts(link))["all_rows"]
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "date", "platform", "surface", "confidence", "evidence", "referrer",
                "device_id", "device_label", "device_confidence", "device_evidence",
                "device_identity_method", "device_identity_confidence", "device_identity_evidence",
                "browser_identity_id", "identity_method", "browser", "os", "model",
                "country", "region", "city", "is_bot", "collection_status", "tracking_version",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
        data = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        return send_file(
            data,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{link.custom_tag}-gateway-v4.2-analytics.csv",
        )

    @app.get("/settings/integration")
    @login_required
    def integration_status():
        status = None
        error = None
        try:
            status = shlink().health()
        except ShlinkError as exc:
            error = str(exc)
        return render_template(
            "dashboard/integration.html",
            active_page="settings",
            status=status,
            error=error,
        )

    @app.route("/settings/password", methods=["GET", "POST"])
    @login_required
    def change_password():
        form = PasswordForm()
        if form.validate_on_submit():
            if not current_user.check_password(form.current_password.data):
                form.current_password.errors.append("Current password is incorrect.")
            else:
                current_user.set_password(form.new_password.data)
                current_user.must_change_password = False
                audit("user.change_password", "user", current_user.id)
                db.session.commit()
                flash("Password changed successfully.", "success")
                return redirect(url_for("dashboard"))
        return render_template("dashboard/change_password.html", form=form, active_page="settings")

    @app.get("/users")
    @login_required
    def users():
        if not current_user.is_admin:
            abort(403)
        return render_template(
            "dashboard/users.html",
            users=User.query.order_by(User.created_at.desc()).all(),
            active_page="users",
        )

    @app.route("/users/new", methods=["GET", "POST"])
    @login_required
    def create_user():
        if not current_user.is_admin:
            abort(403)
        form = UserForm()
        if form.validate_on_submit():
            username = form.username.data.strip().lower()
            email = form.email.data.strip().lower() if form.email.data else None
            if User.query.filter_by(username=username).first():
                form.username.errors.append("That username already exists.")
            elif email and User.query.filter(func.lower(User.email) == email).first():
                form.email.errors.append("That email already exists.")
            elif not form.password.data:
                form.password.errors.append("Enter a temporary password.")
            else:
                user = User(
                    username=username,
                    display_name=form.display_name.data.strip(),
                    email=email,
                    role=form.role.data,
                    is_active=form.is_active.data,
                    must_change_password=form.must_change_password.data,
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.flush()
                audit("user.create", "user", user.id)
                db.session.commit()
                flash("User created.", "success")
                return redirect(url_for("users"))
        return render_template("dashboard/user_form.html", form=form, page_title="Create user", active_page="users")

    @app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_user(user_id):
        if not current_user.is_admin:
            abort(403)
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        form = UserForm(obj=user)
        if request.method == "GET":
            form.password.data = ""
        if form.validate_on_submit():
            username = form.username.data.strip().lower()
            duplicate = User.query.filter(func.lower(User.username) == username, User.id != user.id).first()
            if duplicate:
                form.username.errors.append("That username already exists.")
            else:
                user.username = username
                user.display_name = form.display_name.data.strip()
                user.email = form.email.data.strip().lower() if form.email.data else None
                user.role = form.role.data
                user.is_active = form.is_active.data
                user.must_change_password = form.must_change_password.data
                if form.password.data:
                    user.set_password(form.password.data)
                audit("user.update", "user", user.id)
                db.session.commit()
                flash("User updated.", "success")
                return redirect(url_for("users"))
        return render_template("dashboard/user_form.html", form=form, page_title="Edit user", active_page="users")

    @app.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
    @login_required
    def reset_password(user_id):
        if not current_user.is_admin:
            abort(403)
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        form = ResetPasswordForm()
        if form.validate_on_submit():
            user.set_password(form.new_password.data)
            user.must_change_password = form.require_change.data
            audit("user.reset_password", "user", user.id)
            db.session.commit()
            flash("Password reset.", "success")
            return redirect(url_for("users"))
        return render_template("dashboard/reset_password.html", form=form, user=user, active_page="users")

    @app.post("/__track/collect/<click_token>")
    @csrf.exempt
    @limiter.limit("240 per minute")
    def collect_tracking_event(click_token):
        event = GatewayClickEvent.query.filter_by(click_token=click_token).first()
        if not event:
            return jsonify(status="missing"), 404
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify(status="invalid"), 400
        safe_payload = {
            "localStorageId": str(payload.get("localStorageId") or "")[:128],
            "fingerprintHash": str(payload.get("fingerprintHash") or "")[:64],
            "documentReferrer": str(payload.get("documentReferrer") or "")[:4000],
            "client": payload.get("client") if isinstance(payload.get("client"), dict) else {},
        }
        _apply_detection(event, safe_payload)
        event.collected = True
        event.collection_status = "enriched"
        db.session.commit()
        return jsonify(status="ok")

    @app.get("/r/<path:short_code>")
    @limiter.exempt
    def local_tracking_redirect(short_code):
        link = ManagedLink.query.filter_by(short_code=short_code, is_active=True).first()
        if not link:
            abort(404)
        if request.method == "HEAD":
            return redirect(link.long_url, code=302)
        return _tracking_response(link)

    @app.get("/<path:short_code>")
    @limiter.exempt
    def public_tracking_redirect(short_code):
        if not _public_host_is_short_domain():
            abort(404)
        link = ManagedLink.query.filter_by(short_code=short_code, is_active=True).first()
        if not link:
            abort(404)
        if request.method == "HEAD":
            return redirect(link.long_url, code=302)
        return _tracking_response(link)

    @app.errorhandler(500)
    def error_500(error):
        request_id = uuid4().hex[:12]
        db.session.rollback()
        app.logger.error(
            "Unhandled application error request_id=%s path=%s error=%r",
            request_id,
            request.path,
            getattr(error, "original_exception", error),
        )
        return render_template("errors/500.html", request_id=request_id), 500

    @app.errorhandler(403)
    def error_403(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def error_404(_error):
        return render_template("errors/404.html"), 404

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        click.echo("Database initialized.")

    @app.cli.command("has-admin")
    def has_admin_command():
        db.create_all()
        if User.query.filter_by(role="admin", is_active=True).first():
            click.echo("Administrator exists.")
            return
        raise click.ClickException("No active administrator exists.")

    @app.cli.command("create-admin-env")
    def create_admin_env_command():
        """Create the first administrator from temporary environment values.

        The Windows launcher uses this command so password entry is handled by
        PowerShell instead of Docker's non-interactive getpass fallback.
        """
        username = (os.getenv("LA_ADMIN_USERNAME") or "").strip().lower()
        display_name = (os.getenv("LA_ADMIN_DISPLAY_NAME") or "Administrator").strip()
        password = os.getenv("LA_ADMIN_PASSWORD") or ""
        if not username:
            raise click.ClickException("LA_ADMIN_USERNAME is required.")
        if len(password) < 12:
            raise click.ClickException("Password must contain at least 12 characters.")
        db.create_all()
        if User.query.filter_by(username=username).first():
            raise click.ClickException("That username already exists.")
        user = User(
            username=username,
            display_name=display_name or "Administrator",
            role="admin",
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator '{username}' created.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--display-name", prompt=True, default="Administrator")
    @click.password_option("--password", confirmation_prompt=True)
    def create_admin_command(username, display_name, password):
        db.create_all()
        username = username.strip().lower()
        if len(password) < 12:
            raise click.ClickException("Password must contain at least 12 characters.")
        if User.query.filter_by(username=username).first():
            raise click.ClickException("That username already exists.")
        user = User(username=username, display_name=display_name.strip(), role="admin", is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator '{username}' created.")

    with app.app_context():
        if app.config.get("AUTO_CREATE_DB"):
            db.create_all()

    return app
