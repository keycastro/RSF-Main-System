from __future__ import annotations

import hmac
import json
import re
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

site = Blueprint("site", __name__)

PROJECTS = [
    {
        "slug": "nexus-properties",
        "name": "Nexus Properties",
        "category": "Real Estate Operations System",
        "subtitle": "Internal Off-Market Property Marketplace",
        "status": "Portfolio case study",
        "summary": (
            "A private marketplace concept that helps a real estate team add, find, "
            "update, reconfirm, and manage off-market property listings in one system."
        ),
        "image": "images/projects/nexus-dashboard.png",
        "tags": ["Property listings", "Search & filters", "Status tracking", "Freshness rules"],
    }
]

SERVICES = [
    {
        "title": "Property Operations Systems",
        "text": "One clear place to manage property records, daily work, team actions, and operational status.",
        "example": "Useful for property managers, apartment operators, and rental teams.",
    },
    {
        "title": "Listing & Inventory Systems",
        "text": "Organize property listings, search and filters, ownership, status, updates, and internal inventory.",
        "example": "Useful when listings are spread across messages, sheets, or separate tools.",
    },
    {
        "title": "Rental Management Workflows",
        "text": "Track tenants, rent status, leases, due dates, follow-ups, and other repeatable rental operations.",
        "example": "Useful for landlords and long-term rental-property businesses.",
    },
    {
        "title": "Maintenance & Vendor Workflows",
        "text": "Move maintenance requests from report to assignment, update, completion, and history.",
        "example": "Useful when requests and vendor work are hard to track from start to finish.",
    },
    {
        "title": "Dashboards & Business Visibility",
        "text": "Bring important records, pending work, deadlines, and status into simple owner and manager views.",
        "example": "Useful when the business needs quick answers without checking several places.",
    },
    {
        "title": "Workflow Automation",
        "text": "Add reminders, status rules, follow-up steps, and other practical automation where it saves manual work.",
        "example": "Useful for repetitive actions that should happen consistently.",
    },
]

TECHNOLOGIES = [
    ("Python", "Backend logic and business rules"),
    ("Flask", "Custom web application structure"),
    ("SQL Databases", "Organized records and relationships"),
    ("HTML & CSS", "Responsive, accessible interfaces"),
    ("JavaScript", "Useful interaction in the browser"),
    ("Git & GitHub", "Version history and stable releases"),
    ("APIs", "Connections to other services when needed"),
    ("Deployment", "Moving a tested system from local build to the web"),
]

PAGE_META = {
    "home": "Key Castro builds custom real estate systems and web applications for rental-property operations.",
    "about": "Learn how Key Castro approaches custom real estate systems: understand the workflow, build the right tool, test it, and hand it over clearly.",
    "services": "Custom property operations systems, listing management, rental workflows, maintenance tracking, dashboards, and workflow automation.",
    "projects": "See custom real estate systems and project case studies built by Key Castro.",
    "skills": "Technologies and development skills used to build custom real estate web applications.",
    "experience": "Development experience focused on complete real estate systems, testing, documentation, and reliable delivery.",
    "contact": "Contact Key Castro to discuss a custom real estate or rental-property system.",
}


def _common_context(page_key: str = "home"):
    base_url = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    canonical_url = f"{base_url}{request.path}" if base_url else ""
    return {
        "projects": PROJECTS,
        "services": SERVICES,
        "technologies": TECHNOLOGIES,
        "contact_email": current_app.config.get("CONTACT_EMAIL"),
        "socials": {
            "linkedin": current_app.config.get("LINKEDIN_URL"),
            "github": current_app.config.get("GITHUB_URL"),
            "youtube": current_app.config.get("YOUTUBE_URL"),
            "facebook": current_app.config.get("FACEBOOK_URL"),
        },
        "environment_label": current_app.config.get("ENVIRONMENT_LABEL", ""),
        "meta_description": PAGE_META.get(page_key, PAGE_META["home"]),
        "canonical_url": canonical_url,
        "public_base_url": base_url,
    }


@site.get("/")
def home():
    return render_template("home.html", title="Custom Real Estate Systems Developer", **_common_context("home"))


@site.get("/about")
def about():
    return render_template("about.html", title="About", **_common_context("about"))


@site.get("/services")
def services():
    return render_template("services.html", title="Services", **_common_context("services"))


@site.get("/projects")
def projects():
    return render_template("projects.html", title="Projects", **_common_context("projects"))


@site.get("/projects/<slug>")
def project_detail(slug: str):
    project = next((item for item in PROJECTS if item["slug"] == slug), None)
    if project is None:
        abort(404)
    template_name = f"projects/{slug.replace('-', '_')}.html"
    return render_template(
        template_name,
        title=project["name"],
        project=project,
        **_common_context("projects"),
    )


@site.get("/skills")
def skills():
    return render_template("skills.html", title="Skills & Technologies", **_common_context("skills"))


@site.get("/experience")
def experience():
    return render_template("experience.html", title="Experience", **_common_context("experience"))


def _csrf_token():
    token = session.get("contact_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["contact_csrf"] = token
    return token


def _valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))


def _store_local_message(record: dict) -> None:
    path = Path(current_app.config["CONTACT_STORAGE_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _send_smtp_message(record: dict) -> None:
    recipient = current_app.config["CONTACT_EMAIL"]
    sender = current_app.config["SMTP_FROM_EMAIL"]
    message = EmailMessage()
    message["Subject"] = f"Website project inquiry from {record['name']}"
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = record["email"]
    company = record.get("company") or "Not provided"
    message.set_content(
        "New website inquiry\n\n"
        f"Name: {record['name']}\n"
        f"Email: {record['email']}\n"
        f"Company: {company}\n\n"
        "Project details:\n"
        f"{record['message']}\n"
    )

    host = current_app.config["SMTP_HOST"]
    port = current_app.config["SMTP_PORT"]
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    use_ssl = current_app.config.get("SMTP_USE_SSL", True)
    use_tls = current_app.config.get("SMTP_USE_TLS", False)

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=15) as smtp:
        if not use_ssl and use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


@site.route("/contact", methods=["GET", "POST"])
def contact():
    context = _common_context("contact")
    context["csrf_token"] = _csrf_token()

    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        expected = session.get("contact_csrf", "")
        if not expected or not sent or not hmac.compare_digest(expected, sent):
            abort(400)

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        company = request.form.get("company", "").strip()
        message = request.form.get("message", "").strip()
        website = request.form.get("website", "").strip()  # honeypot

        errors = []
        if website:
            return redirect(url_for("site.contact"))
        if not 2 <= len(name) <= 100:
            errors.append("Please enter your name.")
        if not _valid_email(email) or len(email) > 160:
            errors.append("Please enter a valid email address.")
        if len(company) > 140:
            errors.append("Company name is too long.")
        if not 20 <= len(message) <= 3000:
            errors.append("Please add a little more detail about the system you need.")

        if errors:
            for item in errors:
                flash(item, "error")
            context["form_data"] = {"name": name, "email": email, "company": company, "message": message}
            return render_template("contact.html", title="Contact", **context), 400

        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "email": email,
            "company": company,
            "message": message,
        }

        mode = current_app.config.get("CONTACT_DELIVERY_MODE", "local")
        try:
            if mode == "smtp":
                _send_smtp_message(record)
                flash("Thanks. Your project details were sent successfully.", "success")
            elif current_app.config.get("ENABLE_LOCAL_CONTACT_STORAGE"):
                _store_local_message(record)
                current_app.logger.info("Local contact message stored for %s", email)
                flash("Saved locally for testing. Public delivery will use the configured business email.", "success")
            else:
                raise RuntimeError("Contact delivery is not configured.")
        except Exception:
            current_app.logger.exception("Contact delivery failed")
            flash("Your message could not be sent right now. Please try again later.", "error")
            context["form_data"] = {"name": name, "email": email, "company": company, "message": message}
            return render_template("contact.html", title="Contact", **context), 503

        session["contact_csrf"] = secrets.token_urlsafe(32)
        return redirect(url_for("site.contact"))

    return render_template("contact.html", title="Contact", **context)


@site.get("/system/health")
def health():
    return jsonify(
        status="ok",
        app=current_app.config.get("APP_NAME", "Key Castro Portfolio"),
        environment=current_app.config.get("ENVIRONMENT_LABEL", "unknown"),
        version="2.0.0",
    )


@site.get("/robots.txt")
def robots():
    if current_app.config.get("ENVIRONMENT_LABEL") != "Production":
        body = "User-agent: *\nDisallow: /"
    else:
        body = "User-agent: *\nAllow: /\nSitemap: " + url_for("site.sitemap", _external=True)
    return current_app.response_class(body, mimetype="text/plain")


@site.get("/sitemap.xml")
def sitemap():
    pages = [
        url_for("site.home", _external=True),
        url_for("site.about", _external=True),
        url_for("site.services", _external=True),
        url_for("site.projects", _external=True),
        url_for("site.skills", _external=True),
        url_for("site.experience", _external=True),
        url_for("site.contact", _external=True),
    ]
    pages.extend(url_for("site.project_detail", slug=item["slug"], _external=True) for item in PROJECTS)
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += "\n".join(f"  <url><loc>{page}</loc></url>" for page in pages)
    body += "\n</urlset>"
    return current_app.response_class(body, mimetype="application/xml")


@site.app_errorhandler(400)
def bad_request(error):
    return render_template("error.html", title="Bad Request", code=400, message="That request could not be completed.", **_common_context()), 400


@site.app_errorhandler(404)
def not_found(error):
    return render_template("error.html", title="Not Found", code=404, message="The page you requested does not exist.", **_common_context()), 404


@site.app_errorhandler(500)
def server_error(error):
    return render_template("error.html", title="Server Error", code=500, message="The website encountered an unexpected error.", **_common_context()), 500
