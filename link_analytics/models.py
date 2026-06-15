from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="analyst")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def can_edit(self):
        return self.role in {"admin", "analyst"}


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class ManagedLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    short_code = db.Column(db.String(255), nullable=False, index=True)
    custom_tag = db.Column(db.String(255), nullable=False, index=True)
    long_url = db.Column(db.Text, nullable=False)
    short_url = db.Column(db.Text, nullable=False)
    domain = db.Column(db.String(255), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    owner = db.relationship("User", backref=db.backref("managed_links", lazy=True))

    __table_args__ = (db.UniqueConstraint("domain", "short_code", name="uq_domain_code"),)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.String(80))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class VisitEvent(db.Model):
    """Privacy-conscious click event captured by the Flask tracking gateway."""

    id = db.Column(db.Integer, primary_key=True)
    managed_link_id = db.Column(
        db.Integer,
        db.ForeignKey("managed_link.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visitor_id = db.Column(db.String(64), nullable=False, index=True)
    source_hint = db.Column(db.String(64))
    referrer = db.Column(db.Text)
    user_agent = db.Column(db.Text)
    ip_hash = db.Column(db.String(64), index=True)
    country = db.Column(db.String(80))
    region = db.Column(db.String(120))
    city = db.Column(db.String(120))
    is_bot = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    link = db.relationship(
        "ManagedLink",
        backref=db.backref("visit_events", lazy=True, cascade="all, delete-orphan"),
    )

    def as_analytics_dict(self):
        return {
            "date": self.created_at.isoformat() if self.created_at else "",
            "referer": self.referrer or "",
            "userAgent": self.user_agent or "",
            "source_hint": self.source_hint or "",
            "visitor_id": self.visitor_id,
            "ip_hash": self.ip_hash or "",
            "country": self.country or "Unknown",
            "region": self.region or "",
            "city": self.city or "",
            "potentialBot": bool(self.is_bot),
        }


class ClickEvent(db.Model):
    """Version 3 click event captured by the same short URL.

    This table is intentionally additive so upgrades from 2.x do not require
    destructive SQLite schema migrations. Legacy VisitEvent records remain
    readable and are merged into analytics.
    """

    __tablename__ = "click_event_v3"

    id = db.Column(db.Integer, primary_key=True)
    click_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    managed_link_id = db.Column(
        db.Integer,
        db.ForeignKey("managed_link.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cookie_id = db.Column(db.String(128), index=True)
    local_storage_id = db.Column(db.String(128), index=True)
    fingerprint_hash = db.Column(db.String(64), index=True)
    ip_hash = db.Column(db.String(64), index=True)

    request_referrer = db.Column(db.Text)
    document_referrer = db.Column(db.Text)
    user_agent = db.Column(db.Text)
    x_requested_with = db.Column(db.String(300))
    sec_ch_ua = db.Column(db.Text)
    sec_ch_platform = db.Column(db.String(120))
    sec_ch_mobile = db.Column(db.String(20))
    sec_ch_model = db.Column(db.String(160))
    client_payload = db.Column(db.Text)

    platform = db.Column(db.String(120), nullable=False, default="Unknown / Hidden")
    surface = db.Column(db.String(80), nullable=False, default="Browser or app")
    confidence = db.Column(db.String(40), nullable=False, default="Unavailable")
    evidence = db.Column(db.String(500))
    device_label = db.Column(db.String(120))
    browser = db.Column(db.String(120))
    os_family = db.Column(db.String(120))
    model = db.Column(db.String(160))

    country = db.Column(db.String(80))
    region = db.Column(db.String(120))
    city = db.Column(db.String(120))
    is_bot = db.Column(db.Boolean, nullable=False, default=False, index=True)
    collected = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    link = db.relationship(
        "ManagedLink",
        backref=db.backref("click_events_v3", lazy=True, cascade="all, delete-orphan"),
    )

    def as_analytics_dict(self):
        try:
            client = __import__("json").loads(self.client_payload or "{}")
        except (TypeError, ValueError):
            client = {}
        return {
            "date": self.created_at.isoformat() if self.created_at else "",
            "referrer": self.request_referrer or "",
            "document_referrer": self.document_referrer or "",
            "user_agent": self.user_agent or "",
            "x_requested_with": self.x_requested_with or "",
            "cookie_id": self.cookie_id or "",
            "local_storage_id": self.local_storage_id or "",
            "fingerprint_hash": self.fingerprint_hash or "",
            "ip_hash": self.ip_hash or "",
            "country": self.country or "Unknown",
            "region": self.region or "",
            "city": self.city or "",
            "platform": self.platform or "Unknown / Hidden",
            "surface": self.surface or "Browser or app",
            "confidence": self.confidence or "Unavailable",
            "evidence": self.evidence or "",
            "device_label": self.device_label or "",
            "browser": self.browser or "",
            "os": self.os_family or "",
            "model": self.model or "",
            "client": client,
            "is_bot": bool(self.is_bot),
        }


class GatewayClickEvent(db.Model):
    """Version 4 click captured only by the Flask single-link gateway.

    It intentionally uses a new table so old Shlink rows and earlier local
    experiments can never contaminate current device or platform analytics.
    """

    __tablename__ = "gateway_click_event_v4"

    id = db.Column(db.Integer, primary_key=True)
    click_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    managed_link_id = db.Column(
        db.Integer,
        db.ForeignKey("managed_link.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cookie_id = db.Column(db.String(128), index=True)
    local_storage_id = db.Column(db.String(128), index=True)
    fingerprint_hash = db.Column(db.String(64), index=True)
    ip_hash = db.Column(db.String(64), index=True)

    request_host = db.Column(db.String(255))
    request_referrer = db.Column(db.Text)
    document_referrer = db.Column(db.Text)
    user_agent = db.Column(db.Text)
    x_requested_with = db.Column(db.String(300))
    sec_ch_ua = db.Column(db.Text)
    sec_ch_platform = db.Column(db.String(120))
    sec_ch_mobile = db.Column(db.String(20))
    sec_ch_model = db.Column(db.String(160))
    sec_fetch_site = db.Column(db.String(40))
    sec_fetch_mode = db.Column(db.String(40))
    client_payload = db.Column(db.Text)

    platform = db.Column(db.String(120), nullable=False, default="Unknown / Hidden")
    surface = db.Column(db.String(80), nullable=False, default="Browser or app")
    confidence = db.Column(db.String(40), nullable=False, default="Hidden")
    evidence = db.Column(db.String(500))
    device_label = db.Column(db.String(120))
    browser = db.Column(db.String(120))
    os_family = db.Column(db.String(120))
    model = db.Column(db.String(160))

    country = db.Column(db.String(80))
    region = db.Column(db.String(120))
    city = db.Column(db.String(120))
    is_bot = db.Column(db.Boolean, nullable=False, default=False, index=True)
    collected = db.Column(db.Boolean, nullable=False, default=False, index=True)
    collection_status = db.Column(db.String(32), nullable=False, default="server-only", index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    link = db.relationship(
        "ManagedLink",
        backref=db.backref("gateway_click_events_v4", lazy=True, cascade="all, delete-orphan"),
    )

    def as_analytics_dict(self):
        try:
            client = __import__("json").loads(self.client_payload or "{}")
        except (TypeError, ValueError):
            client = {}
        return {
            "date": self.created_at.isoformat() if self.created_at else "",
            "referrer": self.request_referrer or "",
            "document_referrer": self.document_referrer or "",
            "user_agent": self.user_agent or "",
            "x_requested_with": self.x_requested_with or "",
            "cookie_id": self.cookie_id or "",
            "local_storage_id": self.local_storage_id or "",
            "fingerprint_hash": self.fingerprint_hash or "",
            "ip_hash": self.ip_hash or "",
            "country": self.country or "Unknown",
            "region": self.region or "",
            "city": self.city or "",
            "platform": self.platform or "Unknown / Hidden",
            "surface": self.surface or "Browser or app",
            "confidence": self.confidence or "Hidden",
            "evidence": self.evidence or "",
            "device_label": self.device_label or "",
            "browser": self.browser or "",
            "os": self.os_family or "",
            "model": self.model or "",
            "client": client,
            "is_bot": bool(self.is_bot),
            "collection_status": self.collection_status or "server-only",
            "tracking_version": "4.2",
        }
