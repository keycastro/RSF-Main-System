import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask

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
        if app.config.get("CONTACT_DELIVERY_MODE") != "smtp":
            raise RuntimeError("Production requires CONTACT_DELIVERY_MODE=smtp.")
        required_smtp = ["SMTP_HOST", "SMTP_FROM_EMAIL"]
        missing = [name for name in required_smtp if not app.config.get(name)]
        if missing:
            raise RuntimeError("Production contact delivery is missing: " + ", ".join(missing))

    from .routes import site
    app.register_blueprint(site)

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
