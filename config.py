from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    CREDENTIAL_VAULT_KEY = os.environ.get("RSF_CREDENTIAL_VAULT_KEY", "").strip()
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "rsf_sales_partner.db"))
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
    ONLINE_MODE = bool(DATABASE_URL.startswith(("postgres://", "postgresql://")))
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5078"))
    SESSION_HOURS = max(1, min(24, int(os.environ.get("SESSION_HOURS", "8"))))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_HOURS)
    SESSION_COOKIE_NAME = "rsf_partner_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1" if ONLINE_MODE else "0") == "1"
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    MESSAGE_UPLOAD_DIR = os.environ.get("MESSAGE_UPLOAD_DIR", "")
    PROFILE_PICTURE_DIR = os.environ.get("PROFILE_PICTURE_DIR", "")
    CLIENT_ATTACHMENT_DIR = os.environ.get("CLIENT_ATTACHMENT_DIR", "")
    BACKUP_DIR = os.environ.get("BACKUP_DIR", "")
    TRUSTED_HOSTS = [h.strip() for h in os.environ.get("TRUSTED_HOSTS", "realtysystemsfoundry.onrender.com,partner-rsf.onrender.com,127.0.0.1,localhost" if ONLINE_MODE else "127.0.0.1,localhost").split(",") if h.strip()]

    # Unified public website + official RSF client email
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", os.environ.get("RSF_EMAIL_ADDRESS", "")).strip()
    ENVIRONMENT_LABEL = os.environ.get("ENVIRONMENT_LABEL", "Local").strip() or "Local"
    LINKEDIN_URL = os.environ.get("LINKEDIN_URL", "").strip()
    GITHUB_URL = os.environ.get("GITHUB_URL", "").strip()
    YOUTUBE_URL = os.environ.get("YOUTUBE_URL", "").strip()
    FACEBOOK_URL = os.environ.get("FACEBOOK_URL", "").strip()
    GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "").strip()
    BING_SITE_VERIFICATION = os.environ.get("BING_SITE_VERIFICATION", "").strip()

    RSF_EMAIL_NAME = os.environ.get("RSF_EMAIL_NAME", "Realty Systems Foundry").strip() or "Realty Systems Foundry"
    RSF_EMAIL_ADDRESS = os.environ.get("RSF_EMAIL_ADDRESS", "").strip()
    SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "").strip()
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "1").strip().lower() in {"1","true","yes","on"}
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "0").strip().lower() in {"1","true","yes","on"}
    IMAP_HOST = os.environ.get("IMAP_HOST", "").strip()
    IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
    IMAP_USERNAME = os.environ.get("IMAP_USERNAME", "").strip()
    IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")
    IMAP_USE_SSL = os.environ.get("IMAP_USE_SSL", "1").strip().lower() in {"1","true","yes","on"}
    IMAP_MAILBOX = os.environ.get("IMAP_MAILBOX", "INBOX").strip() or "INBOX"

    # Unified operations automation
    AUTO_EMAIL_SYNC = os.environ.get("AUTO_EMAIL_SYNC", "1").strip().lower() in {"1","true","yes","on"}
    EMAIL_SYNC_INTERVAL_SECONDS = max(30, min(900, int(os.environ.get("EMAIL_SYNC_INTERVAL_SECONDS", "60"))))
    FIRST_RESPONSE_SLA_MINUTES = max(5, min(1440, int(os.environ.get("FIRST_RESPONSE_SLA_MINUTES", "60"))))
    CLIENT_MAX_ATTACHMENTS = max(1, min(10, int(os.environ.get("CLIENT_MAX_ATTACHMENTS", "5"))))
    CLIENT_MAX_FILE_MB = max(1, min(25, int(os.environ.get("CLIENT_MAX_FILE_MB", "15"))))
    CLIENT_MAX_TOTAL_MB = max(1, min(50, int(os.environ.get("CLIENT_MAX_TOTAL_MB", "25"))))
    AUTO_BACKUP_INTERVAL_HOURS = max(1, min(168, int(os.environ.get("AUTO_BACKUP_INTERVAL_HOURS", "24"))))
