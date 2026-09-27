from __future__ import annotations

import os
import secrets
import string
from pathlib import Path

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
        present = set()
        for raw in text.splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                present.add(line.split("=", 1)[0].strip())
        additions = []
        for key, value in defaults.items():
            if key not in present:
                additions.append(f"{key}={value}")
        secret_value = ""
        for raw in text.splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and line.startswith("SECRET_KEY="):
                secret_value = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        if "SECRET_KEY" not in present:
            secret_value = secrets.token_urlsafe(48)
            additions.insert(0, f"SECRET_KEY={secret_value}")
        if "RSF_CREDENTIAL_VAULT_KEY" not in present:
            # Existing v1.9.4 builds fall back to SECRET_KEY for vault encryption.
            # Reusing that value here preserves decryptability while making the key explicit.
            if not secret_value:
                secret_value = secrets.token_urlsafe(48)
            additions.insert(1 if additions and additions[0].startswith("SECRET_KEY=") else 0,
                             f"RSF_CREDENTIAL_VAULT_KEY={secret_value}")
        if additions:
            ENV_PATH.write_text(text.rstrip() + "\n\n# Unified RSF website + credential visibility\n" + "\n".join(additions) + "\n", encoding="utf-8")
        return
    secret = secrets.token_urlsafe(48)
    lines = [f"SECRET_KEY={secret}", f"RSF_CREDENTIAL_VAULT_KEY={secrets.token_urlsafe(48)}"] + [f"{key}={value}" for key, value in defaults.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
            return password


def main() -> None:
    ensure_env()
    # Import only after .env exists so config loads the generated key.
    from app import create_app
    from app.auth import hash_password
    from app.credential_vault import store_password, seed_password_if_matches
    from app.db import ensure_database, get_db
    from app.services import utcnow_iso

    app = create_app()
    with app.app_context():
        ensure_database()
        db = get_db()
        admin = db.execute("SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        if admin:
            seeded = 0
            founder_seed = os.environ.get("RSF_VAULT_SEED_FOUNDER_PASSWORD", "")
            if founder_seed and seed_password_if_matches(db, admin["id"], founder_seed):
                seeded += 1
            partner_seed = os.environ.get("RSF_VAULT_SEED_PARTNER_PASSWORD", "")
            if partner_seed:
                partner = db.execute("SELECT id FROM users WHERE role='partner' AND active=1 ORDER BY id LIMIT 1").fetchone()
                if partner and seed_password_if_matches(db, partner["id"], partner_seed):
                    seeded += 1
            if seeded:
                db.commit()
                print(f"Founder password visibility vault seeded for {seeded} existing account(s).")
            if FIRST_ACCESS.exists():
                try:
                    FIRST_ACCESS.unlink()
                except OSError:
                    pass
            print("Database ready. Existing Founder account preserved.")
            return
        password = generate_password()
        now = utcnow_iso()
        cur = db.execute(
            """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
               VALUES (?,?,?,'admin',1,0,?,?)""",
            ("RSF Founder", "founder@rsf.local", hash_password(password), now, now),
        )
        store_password(db, cur.lastrowid, password)
        db.commit()
        text = (
            "UNIFIED RSF SYSTEM — FIRST FOUNDER ACCESS\n"
            "\n"
            "Name: RSF Founder\n"
            f"Password: {password}\n"
            "\n"
            "You can keep this password or change it later from Account & Security.\n"
            "Delete this file after you save the login somewhere safe.\n"
        )
        FIRST_ACCESS.write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
