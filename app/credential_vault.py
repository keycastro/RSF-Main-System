from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from werkzeug.security import check_password_hash

from .services import utcnow_iso


def _fernet() -> Fernet:
    secret = (current_app.config.get("CREDENTIAL_VAULT_KEY") or current_app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("RSF credential vault key is not configured.")
    # Accept any high-entropy application secret while giving Fernet the 32-byte URL-safe key it requires.
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
    db.execute(
        """INSERT INTO account_password_vault(user_id,encrypted_password,updated_at)
           VALUES (?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET encrypted_password=excluded.encrypted_password,updated_at=excluded.updated_at""",
        (user_id, encrypted, now),
    )


def current_password(db, user_id: int) -> str | None:
    row = db.execute(
        "SELECT encrypted_password FROM account_password_vault WHERE user_id=?",
        (user_id,),
    ).fetchone()
    return decrypt_password(row["encrypted_password"]) if row else None


def seed_password_if_matches(db, user_id: int, password: str) -> bool:
    if not password:
        return False
    user = db.execute("SELECT id,password_hash FROM users WHERE id=?", (user_id,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return False
    store_password(db, user_id, password)
    return True
