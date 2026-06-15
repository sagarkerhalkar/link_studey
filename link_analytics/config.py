import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    APP_NAME = os.getenv("APP_NAME", "Link Analytics")
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-before-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'dashboard.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "1") == "1"

    SHLINK_API_URL = os.getenv("SHLINK_API_URL", "http://127.0.0.1:2332").rstrip("/")
    SHLINK_API_KEY = os.getenv("SHLINK_API_KEY", "")
    SHLINK_DOMAIN = os.getenv("SHLINK_DOMAIN", "s.sagarkerhalkar.com")
    SHLINK_VERIFY_TLS = os.getenv("SHLINK_VERIFY_TLS", "1") == "1"
    SHLINK_TIMEOUT_SECONDS = float(os.getenv("SHLINK_TIMEOUT_SECONDS", "12"))
    PUBLIC_SHORT_BASE_URL = os.getenv(
        "PUBLIC_SHORT_BASE_URL", f"https://{SHLINK_DOMAIN}"
    ).rstrip("/")

    TRUST_PROXY = os.getenv("TRUST_PROXY", "1") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
