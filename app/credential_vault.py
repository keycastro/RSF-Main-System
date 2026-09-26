from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from werkzeug.security import check_password_hash

from .services import utcnow_iso


def _fernet() -> Fernet:
    secret = (current_app.config.get("CREDENTIAL_VAULT_KEY") or current_app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("RSF credential vault key is not configured.")
    material = hashlib.sha256(("rsf-account-password-vault-v1:" + secret).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    return _fernet().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(token: str) -> str:
    try:
        return _fernet().decrypt((token or "").encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Stored account password could not be decrypted with the configured RSF vault key.") from exc


def store_password(db, user_id: int, password: str) -> None:
    encrypted = encrypt_password(password)
    now = utcnow_iso()
    key = f"account_password_vault:{int(user_id)}"
    db.execute(
        """INSERT INTO settings(key,value,updated_at) VALUES (?,?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
        (key, encrypted, now),
    )


def current_password(db, user_id: int) -> str | None:
    key = f"account_password_vault:{int(user_id)}"
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return decrypt_password(row["value"]) if row else None


def seed_password_if_matches(db, user_id: int, password: str) -> bool:
    if not password:
        return False
    user = db.execute("SELECT id,password_hash FROM users WHERE id=?", (user_id,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return False
    store_password(db, user_id, password)
    return True


def one_time_sync_from_environment(db) -> tuple[int, int]:
    """Synchronize explicitly supplied account passwords once during a controlled deployment.

    The JSON payload is never persisted as plaintext. Existing users are updated to the
    supplied exact password hash and the separately encrypted Founder-visible vault copy.
    """
    if os.environ.get("RSF_ONE_TIME_ACCOUNT_PASSWORD_SYNC", "0").strip() != "1":
        return 0, 0
    raw = os.environ.get("RSF_ACCOUNT_PASSWORD_SYNC_JSON", "").strip()
    if not raw:
        return 0, 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("RSF_ACCOUNT_PASSWORD_SYNC_JSON is invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("RSF_ACCOUNT_PASSWORD_SYNC_JSON must be an object mapping email to password.")

    from .auth import hash_password

    synced = 0
    missing = 0
    now = utcnow_iso()
    for email, password in payload.items():
        email = str(email or "").strip().lower()
        password = str(password or "")
        if not email or not password:
            continue
        user = db.execute(
            "SELECT id,email,password_hash,role,active FROM users WHERE lower(email)=? AND active=1 LIMIT 1",
            (email,),
        ).fetchone()
        if not user:
            missing += 1
            continue

        already_current = check_password_hash(user["password_hash"], password)
        existing = current_password(db, int(user["id"]))
        if not already_current:
            db.execute(
                """UPDATE users SET password_hash=?,force_password_change=0,failed_login_count=0,
                   locked_until=NULL,updated_at=? WHERE id=?""",
                (hash_password(password), now, user["id"]),
            )
        if existing != password:
            store_password(db, int(user["id"]), password)
        synced += 1

    if synced:
        db.commit()
    return synced, missing
