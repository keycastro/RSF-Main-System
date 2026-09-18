import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, request

from config import CONFIG_MAP


def create_app(config_name: str | None = None):
    selected = (config_name or os.getenv("APP_ENV", "development")).lower()
    config_class = CONFIG_MAP.get(selected, CONFIG_MAP["development"])

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    if selected == "production":
        if app.config["SECRET_KEY"] in {"", "local-dev-change-me"}:
            raise RuntimeError("Production requires a strong SECRET_KEY in the environment.")
        if not app.config.get("TRUSTED_HOSTS"):
            raise RuntimeError("Production requires TRUSTED_HOSTS to be configured.")
        if not app.config.get("PUBLIC_BASE_URL"):
            raise RuntimeError("Production requires PUBLIC_BASE_URL to be configured.")
        if not app.config.get("CONTACT_EMAIL"):
            raise RuntimeError("Production requires CONTACT_EMAIL to be configured.")
        if not app.config.get("DATABASE_URL"):
            raise RuntimeError("Production requires DATABASE_URL for the private inquiry inbox.")
        if not app.config.get("OWNER_INBOX_TOKEN"):
            raise RuntimeError("Production requires OWNER_INBOX_TOKEN for the private owner API.")

    from .routes import site
    from .owner import owner
    app.register_blueprint(site)
    app.register_blueprint(owner)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'",
        )
        if request.path.startswith(("/__owner_api/", "/__owner_access/", "/owner/")):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    configure_logging(app)
    return app


def configure_logging(app: Flask):
    if app.testing:
        return
    project_root = Path(app.root_path).parent
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "website.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setLevel("INFO")
    handler.setFormatter(app.logger.handlers[0].formatter if app.logger.handlers else None)
    app.logger.addHandler(handler)
    app.logger.setLevel("INFO")
