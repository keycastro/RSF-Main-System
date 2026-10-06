"""Verify the current RSF install without changing production data."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["RSF_DISABLE_BACKGROUND"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.auth import valid_password
from app.db import get_db


def fail(message: str) -> None:
    raise SystemExit("VERIFY FAILED: " + message)


def main() -> int:
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    if version != "1.18.230":
        fail(f"Expected version 1.18.230, found {version or 'empty'}.")

    source_files = [
        ROOT / "config.py",
        ROOT / "requirements.txt",
        ROOT / "app" / "routes.py",
        ROOT / "app" / "templates" / "account_security.html",
        ROOT / "app" / "static" / "js" / "app.js",
    ]
    source = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in source_files)
    for forbidden in (
        "account_security_reveal_password",
        "data-vault-reveal",
        "data-vault-copy",
    ):
        if forbidden in source:
            fail(f"Retired security/integration artifact remains: {forbidden}")

    for required in (
        "RETELL_API_KEY",
        "RETELL_AGENT_ID",
        "RETELL_FROM_NUMBER",
        "retell-sdk==6.0.1",
        "def prospect_ai_call",
        "def retell_webhook",
    ):
        if required not in source:
            fail(f"Required Retell integration artifact is missing: {required}")

    if not valid_password("twelve-chars!"):
        fail("12+ character password validation is not active.")
    if valid_password("short"):
        fail("Short passwords are still accepted.")

    with tempfile.TemporaryDirectory(prefix="rsf-current-verifier-") as td:
        root = Path(td)
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "verify-only-secret",
            "DATABASE_URL": "",
            "DATABASE": str(root / "verify.db"),
            "MESSAGE_UPLOAD_DIR": str(root / "message_uploads"),
            "PROFILE_PICTURE_DIR": str(root / "profile_pictures"),
            "CLIENT_ATTACHMENT_DIR": str(root / "client_attachments"),
            "BACKUP_DIR": str(root / "backups"),
            "TRUSTED_HOSTS": ["localhost", "127.0.0.1"],
            "SESSION_COOKIE_SECURE": False,
        })
        client = app.test_client()

        health = client.get("/system/health")
        if health.status_code != 200 or health.get_json().get("version") != version:
            fail("Health endpoint/version check failed.")

        with app.app_context():
            db = get_db()
            tables = {row["name"] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            if "account_password_vault" in tables:
                fail("Recoverable password-vault table still exists.")
            if "ai_sales_calls" not in tables:
                fail("AI-call storage table is missing.")
            migration = db.execute(
                "SELECT name FROM schema_migrations WHERE version=43"
            ).fetchone()
            if not migration:
                fail("Security migration 43 was not applied.")

        if client.post("/app/webhooks/whatsapp", data=b"{}").status_code == 400:
            fail("WhatsApp provider callback is still blocked by browser CSRF.")
        if client.post("/app/webhooks/twilio/manual-call/not-real/twiml").status_code == 400:
            fail("Twilio provider callback is still blocked by browser CSRF.")
        if client.post("/app/integrations/retell/webhook", data=b"{}").status_code != 401:
            fail("Retell signed webhook did not reach provider authentication.")

        services = client.get("/services")
        if services.status_code != 200:
            fail("Services page did not load.")
        for retired in (b"$199", b"$79", b"$149"):
            if retired in services.data:
                fail(f"Retired public pricing remains: {retired.decode()}")

    print("RSF CURRENT INSTALL VERIFICATION PASSED")
    print("Version:", version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
