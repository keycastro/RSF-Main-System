from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import os
from flask import Flask, g, redirect, render_template, request, url_for

from config import Config, BASE_DIR
from . import db
from .auth import csrf_token, load_logged_in_user, validate_csrf
from .services import setting


def _read_version() -> str:
    try:
        return (BASE_DIR / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _human_status(value: str | None) -> str:
    return (value or "").replace("_", " ").title()


def _money(cents: int | None) -> str:
    value = int(cents or 0) / 100
    return f"{value:,.2f}"


def _rate(bp: int | None) -> str:
    value = (int(bp or 0) / 100)
    return f"{value:g}%"


def _currency_symbol(code: str | None) -> str:
    mapping = {
        "USD": "$",
        "PHP": "₱",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "AUD": "A$",
        "CAD": "C$",
        "SGD": "S$",
        "HKD": "HK$",
    }
    normalized = (code or "USD").strip().upper()
    return mapping.get(normalized, normalized)


def _fmt_money(cents: int | None, has_data: bool = True, currency_code: str | None = "USD") -> str:
    if not has_data or cents is None:
        return "—"
    value = int(cents) / 100
    return f"{_currency_symbol(currency_code)}{value:,.2f}"


def _fmt_count(value: int | None, has_data: bool = True) -> str:
    if not has_data or value is None:
        return "—"
    return f"{int(value):,}"


def _dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo:
            parsed = parsed.astimezone()
        return parsed.strftime("%b %d, %Y · %I:%M %p").replace(" 0", " ")
    except Exception:
        return value.replace("T", " ")


def _date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %Y").replace(" 0", " ")
    except Exception:
        return value


def _chat_dt(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo:
            parsed = parsed.astimezone()
        now = datetime.now().astimezone()
        time_text = parsed.strftime("%I:%M %p").lstrip("0")
        if parsed.date() == now.date():
            return time_text
        if (now.date() - parsed.date()).days == 1:
            return f"Yesterday · {time_text}"
        if parsed.year == now.year:
            return f"{parsed.strftime('%b %d').replace(' 0', ' ')} · {time_text}"
        return parsed.strftime("%b %d, %Y").replace(" 0", " ")
    except Exception:
        return value.replace("T", " ")


def _profile_picture_url(user_id: int | None, role: str | None = None) -> str:
    if not user_id:
        return ""
    try:
        row = db.get_db().execute(
            "SELECT role,avatar_stored_name FROM users WHERE id=?", (int(user_id),)
        ).fetchone()
    except Exception:
        row = None
    if row and row["avatar_stored_name"]:
        return url_for("main.profile_picture", user_id=int(user_id))
    effective_role = (row["role"] if row else role) or ""
    if effective_role == "admin":
        return url_for("static", filename="images/about/key-castro.png")
    return ""


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    storage_root = Path(app.instance_path) if app.config.get("DATABASE_URL") else Path(app.config["DATABASE"]).parent
    if not app.config.get("MESSAGE_UPLOAD_DIR"):
        app.config["MESSAGE_UPLOAD_DIR"] = str(storage_root / "message_uploads")
    if not app.config.get("PROFILE_PICTURE_DIR"):
        app.config["PROFILE_PICTURE_DIR"] = str(storage_root / "profile_pictures")
    if not app.config.get("CLIENT_ATTACHMENT_DIR"):
        app.config["CLIENT_ATTACHMENT_DIR"] = str(storage_root / "client_attachments")
    if not app.config.get("BACKUP_DIR"):
        app.config["BACKUP_DIR"] = str(storage_root / "backups")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get("SECRET_KEY"):
        if app.config.get("TESTING"):
            app.config["SECRET_KEY"] = "test-only-rsf-secret"
        else:
            raise RuntimeError("SECRET_KEY is not configured. Run bootstrap.py or the Windows setup first.")

    app.config["VERSION"] = _read_version()
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def serialize_writes():
        # Lock before reading authorization or business state. SQLite otherwise
        # starts its write transaction only after these checks have already run.
        if request.method == "POST" and request.blueprint == "main":
            validate_csrf()
            try:
                db.get_db().execute("BEGIN IMMEDIATE")
            except (sqlite3.OperationalError, db.OperationalError) as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                return render_template("error.html", title="System busy", code=503,
                                       message="The system is busy. Try again in a moment."), 503, {"Retry-After": "5"}

    app.before_request(load_logged_in_user)

    app.jinja_env.filters.update(human_status=_human_status, money=_money, rate=_rate, dt=_dt, dateonly=_date, chatdt=_chat_dt)
    app.jinja_env.globals.update(
        csrf_token=csrf_token,
        app_version=app.config["VERSION"],
        current_year=datetime.now(timezone.utc).year,
        setting=setting,
        currency_symbol=_currency_symbol,
        fmt_money=_fmt_money,
        fmt_count=_fmt_count,
        profile_picture_url=_profile_picture_url,
    )

    from .public_routes import site
    from .routes import bp
    app.register_blueprint(site)
    app.register_blueprint(bp, url_prefix="/app")

    with app.app_context():
        db.ensure_database()
        from .credential_vault import one_time_sync_from_environment
        one_time_sync_from_environment(db.get_db())

    # Background mailbox sync + protected local/off-site-capable backups. A DB lease
    # ensures only one worker is active even when multiple WSGI workers are running.
    if not app.config.get("TESTING") and os.environ.get("RSF_DISABLE_BACKGROUND", "0") != "1":
        from .background import start_background_services
        start_background_services(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=(), payment=(), usb=()")
        response.headers.setdefault("X-RSF-App", "partner-system")
        if request.blueprint == "site":
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                "font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            )
            response.headers.setdefault("Cache-Control", "public, max-age=300")
        else:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
                "font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            )
            response.headers.setdefault("Cache-Control", "no-store, private, max-age=0")
        return response

    @app.errorhandler(400)
    def bad_request(error):
        # Werkzeug rejects untrusted Host headers before Flask can create a usable
        # URL adapter. Rendering our normal error template in that state calls
        # url_for() and can turn the intended 400 into an internal error. Keep
        # hostile-host failures deliberately minimal and dependency-free.
        from werkzeug.exceptions import SecurityError
        if isinstance(error, SecurityError):
            return "Bad Request", 400, {"Content-Type": "text/plain; charset=utf-8"}
        return render_template("error.html", title="Something went wrong", code=400, message=getattr(error, "description", "We could not process that request.")), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", title="Access denied", code=403, message="You do not have access to this page or action."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", title="Not found", code=404, message="We could not find that page or record."), 404

    @app.errorhandler(413)
    def too_large(_error):
        if request.headers.get("X-RSF-Async") == "1":
            return {"ok": False, "error": "Attachments are too large."}, 413
        return render_template("error.html", title="Request too large", code=413, message="That request is too large."), 413

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", title="System error", code=500, message="Something went wrong. Please try again."), 500

    return app
