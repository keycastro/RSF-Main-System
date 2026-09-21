import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    APP_NAME = "Realty Systems Foundry"
    SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-change-me")
    SESSION_COOKIE_NAME = "key_castro_portfolio_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 256 * 1024

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "").strip()
    LINKEDIN_URL = os.getenv("LINKEDIN_URL", "").strip()
    GITHUB_URL = os.getenv("GITHUB_URL", "").strip()
    YOUTUBE_URL = os.getenv("YOUTUBE_URL", "").strip()
    FACEBOOK_URL = os.getenv("FACEBOOK_URL", "").strip()
    GOOGLE_SITE_VERIFICATION = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
    BING_SITE_VERIFICATION = os.getenv("BING_SITE_VERIFICATION", "").strip()

    CONTACT_DELIVERY_MODE = os.getenv("CONTACT_DELIVERY_MODE", "local").strip().lower()
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    OWNER_INBOX_TOKEN = os.getenv("OWNER_INBOX_TOKEN", "").strip()
    OWNER_TIMEZONE = os.getenv("OWNER_TIMEZONE", "Asia/Manila").strip() or "Asia/Manila"
    ENABLE_LOCAL_CONTACT_STORAGE = _env_bool("ENABLE_LOCAL_CONTACT_STORAGE", "1")
    CONTACT_STORAGE_PATH = os.getenv(
        "CONTACT_STORAGE_PATH", str(BASE_DIR / "instance" / "contact_messages.jsonl")
    )

    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
    SMTP_USE_SSL = _env_bool("SMTP_USE_SSL", "1")
    SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", "0")


class DevelopmentConfig(BaseConfig):
    ENVIRONMENT_LABEL = "Local"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = False
    TRUSTED_HOSTS = ["127.0.0.1", "localhost"]


class TestingConfig(BaseConfig):
    ENVIRONMENT_LABEL = "Test"
    DEBUG = False
    TESTING = True
    SESSION_COOKIE_SECURE = False
    SERVER_NAME = "localhost"
    ENABLE_LOCAL_CONTACT_STORAGE = False
    CONTACT_DELIVERY_MODE = "local"
    DATABASE_URL = ""
    OWNER_INBOX_TOKEN = "test-owner-token"


class ProductionConfig(BaseConfig):
    ENVIRONMENT_LABEL = "Production"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    TRUSTED_HOSTS = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()]


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "local": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
