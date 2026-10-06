from __future__ import annotations

import secrets
import string
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
FIRST_ACCESS = BASE_DIR / "FIRST_RUN_FOUNDER_ACCESS.txt"


def ensure_env() -> None:
    defaults = {
        "HOST": "127.0.0.1",
        "PORT": "5078",
        "SESSION_HOURS": "8",
        "TRUSTED_HOSTS": "127.0.0.1,localhost",
        "SESSION_COOKIE_SECURE": "0",
        "PUBLIC_BASE_URL": "",
        "CONTACT_EMAIL": "",
        "ENVIRONMENT_LABEL": "Local",
        "RSF_EMAIL_NAME": "Realty Systems Foundry",
        "RSF_EMAIL_ADDRESS": "",
        "SMTP_HOST": "",
        "SMTP_PORT": "465",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "SMTP_USE_SSL": "1",
        "SMTP_USE_TLS": "0",
        "IMAP_HOST": "",
        "IMAP_PORT": "993",
        "IMAP_USERNAME": "",
        "IMAP_PASSWORD": "",
        "IMAP_USE_SSL": "1",
        "IMAP_MAILBOX": "INBOX",
    }
    if ENV_PATH.exists():
        text = ENV_PATH.read_text(encoding="utf-8-sig", errors="replace")
        present = {
            line.split("=", 1)[0].strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "=" in line
        }
        additions = []
        if "SECRET_KEY" not in present:
            additions.append(f"SECRET_KEY={secrets.token_urlsafe(48)}")
        additions.extend(f"{key}={value}" for key, value in defaults.items() if key not in present)
        if additions:
            ENV_PATH.write_text(
                text.rstrip() + "\n\n# RSF runtime configuration\n" + "\n".join(additions) + "\n",
                encoding="utf-8",
            )
        return

    lines = [f"SECRET_KEY={secrets.token_urlsafe(48)}"] + [
        f"{key}={value}" for key, value in defaults.items()
    ]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
            return password


def main() -> None:
    ensure_env()
    from app import create_app
    from app.auth import hash_password
    from app.db import ensure_database, get_db
    from app.services import utcnow_iso

    app = create_app()
    with app.app_context():
        ensure_database()
        db = get_db()
        admin = db.execute("SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        if admin:
            if FIRST_ACCESS.exists():
                try:
                    FIRST_ACCESS.unlink()
                except OSError:
                    pass
            print("Database ready. Existing Founder account preserved.")
            return

        password = generate_password()
        founder_email = (os.environ.get("FOUNDER_EMAIL") or "founder@rsf.local").strip().lower()
        now = utcnow_iso()
        db.execute(
            """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
               VALUES (?,?,?,'admin',1,0,?,?)""",
            ("RSF Founder", founder_email, hash_password(password), now, now),
        )
        db.commit()
        text = (
            "UNIFIED RSF SYSTEM — FIRST FOUNDER ACCESS\n\n"
            "Name: RSF Founder\n"
            f"Email: {founder_email}\n"
            f"Password: {password}\n\n"
            "Save this password somewhere secure. RSF stores only its secure hash and cannot reveal it later.\n"
            "Delete this file after you save the login.\n"
        )
        FIRST_ACCESS.write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
