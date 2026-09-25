from __future__ import annotations

import functools
import hmac
import hashlib
import re
from datetime import datetime, timedelta, timezone

from flask import abort, current_app, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hash_password(password: str) -> str:
    method = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt")
    return generate_password_hash(password, method=method)


def valid_password(password: str) -> bool:
    return len(password or "") >= 12 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)


def valid_email(value: str) -> bool:
    return len(value or "") <= 254 and bool(EMAIL_RE.fullmatch((value or "").strip()))


def session_credential(user) -> str:
    # Bind sessions to credentials without exposing the password hash in cookies.
    return hmac.new(current_app.secret_key.encode(), user["password_hash"].encode(), hashlib.sha256).hexdigest()


def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    if not user_id:
        g.user = None
        g.partner = None
        return
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if user is None or not user["active"] or not hmac.compare_digest(
        session.get("credential", ""), session_credential(user)
    ):
        session.clear()
        g.user = None
        g.partner = None
        return
    g.user = user
    g.partner = None
    if user["role"] == "partner":
        g.partner = db.execute(
            """SELECT p.*, cs.name AS commission_stage_name, cs.rate_bp AS commission_rate_bp
               FROM partners p JOIN commission_stages cs ON cs.id=p.commission_stage_id
               WHERE p.user_id=? AND p.active=1""",
            (user["id"],),
        ).fetchone()
        if g.partner is None:
            session.clear()
            g.user = None


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return redirect(url_for("main.login", next=request.path))
        return view(**kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return redirect(url_for("main.login", next=request.path))
        if g.user["role"] != "admin":
            abort(403)
        return view(**kwargs)
    return wrapped


def csrf_token() -> str:
    import secrets
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf() -> None:
    expected = session.get("csrf_token", "")
    received = request.form.get("csrf_token", "")
    if not expected or not received or not hmac.compare_digest(expected.encode(), received.encode()):
        abort(400, description="This form expired. Refresh the page and try again.")


def authenticate(email: str, password: str):
    db = get_db()
    email = (email or "").strip().lower()
    user = db.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
    now = datetime.now(timezone.utc)
    if user is None or not user["active"]:
        return None, "Invalid email or password."
    if user["locked_until"]:
        try:
            locked_until = datetime.fromisoformat(user["locked_until"])
            if locked_until > now:
                return None, "Too many sign-in attempts. Try again in a few minutes."
        except ValueError:
            pass
    if not check_password_hash(user["password_hash"], password or ""):
        failures = int(user["failed_login_count"] or 0) + 1
        locked_until = None
        if failures >= 5:
            locked_until = (now + timedelta(minutes=10)).replace(microsecond=0).isoformat()
            failures = 0
        db.execute(
            "UPDATE users SET failed_login_count=?, locked_until=?, updated_at=? WHERE id=?",
            (failures, locked_until, utcnow_iso(), user["id"]),
        )
        db.commit()
        return None, "Invalid email or password."
    db.execute(
        "UPDATE users SET failed_login_count=0, locked_until=NULL, last_login_at=?, updated_at=? WHERE id=?",
        (utcnow_iso(), utcnow_iso(), user["id"]),
    )
    db.commit()
    return user, None


def login_user(user) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["credential"] = session_credential(user)
    session.permanent = True


def safe_next(value: str | None) -> str | None:
    if (value and value.startswith("/") and not value.startswith("//")
            and "\\" not in value and not any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return value
    return None
