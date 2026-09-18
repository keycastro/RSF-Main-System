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

from .inquiries import create_inquiry
from .seo import (
    absolute_url,
    breadcrumb_structured_data,
    core_structured_data,
    software_template_structured_data,
)
from .system_templates import get_system_template, published_templates, template_library_enabled

site = Blueprint("site", __name__)

SERVICES = [
    {
        "title": "Property & Listing Operations",
        "text": "Centralize property records, internal listings, ownership, status, search, and day-to-day operational work.",
        "example": "Useful for property managers, brokerages, apartment operators, and teams managing shared inventory.",
    },
    {
        "title": "Rental & Tenant Workflows",
        "text": "Track tenants, leases, rent status, due dates, follow-ups, and repeatable long-term rental processes.",
        "example": "Useful for landlords and rental-property businesses that need a clearer operating system.",
    },
    {
        "title": "Maintenance & Team Coordination",
        "text": "Move requests from report to assignment, update, completion, vendor coordination, and history.",
        "example": "Useful when maintenance and team actions are spread across messages or separate trackers.",
    },
    {
        "title": "Dashboards & Workflow Automation",
        "text": "Show what needs attention and add practical reminders, status rules, and follow-up automation where it saves manual work.",
        "example": "Useful when owners and managers need faster visibility and more consistent follow-through.",
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

PAGE_SEO = {
    "home": {
        "title": "Custom Real Estate Systems Developer | Key Castro",
        "description": "Key Castro builds custom real estate systems and offers completed standard templates for property operations, inventory, rental, maintenance, and team workflows.",
    },
    "about": {
        "title": "About Key Castro | Custom Real Estate Systems Developer",
        "description": "Learn how Key Castro approaches custom real estate systems: understand the workflow, build the right tool, test it, and hand it over clearly.",
    },
    "services": {
        "title": "Custom Real Estate Software Services | Key Castro",
        "description": "Custom property operations systems, listing management, rental workflows, maintenance tracking, dashboards, and workflow automation.",
    },
    "projects": {
        "title": "Real Estate Software Projects & Case Studies | Key Castro",
        "description": "Explore completed real estate systems built by Key Castro, including free standard templates for property operations and private property inventory.",
    },
    "skills": {
        "title": "Skills & Technology | Key Castro",
        "description": "Technologies and development skills used by Key Castro to build custom real estate web applications and business systems.",
    },
    "experience": {
        "title": "Development Experience | Key Castro",
        "description": "Development experience focused on complete real estate systems, testing, documentation, and reliable delivery.",
    },
    "contact": {
        "title": "Contact Key Castro | Discuss a Custom Real Estate System",
        "description": "Contact Key Castro to request a free standard system template or discuss paid customization and custom real estate software development.",
    },
    "system_templates": {
        "title": "Real Estate System Templates | Key Castro",
        "description": "Explore reusable real estate system templates built by Key Castro, with workflows, demonstrations, screenshots, and customization options.",
    },
}


def _common_context(
    page_key: str = "home",
    *,
    seo_title: str | None = None,
    meta_description: str | None = None,
    og_image: str | None = None,
    og_image_alt: str | None = None,
    extra_structured_data: list[dict] | None = None,
    indexable: bool = True,
):
    base_url = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    canonical_url = f"{base_url}{request.path}" if base_url and indexable else ""
    socials = {
        "linkedin": current_app.config.get("LINKEDIN_URL"),
        "github": current_app.config.get("GITHUB_URL"),
        "youtube": current_app.config.get("YOUTUBE_URL"),
        "facebook": current_app.config.get("FACEBOOK_URL"),
    }
    page_meta = PAGE_SEO.get(page_key, PAGE_SEO["home"])
    og_image_path = og_image or "images/templates/property-operations-command-center/dashboard.png"
    og_image_url = absolute_url(base_url, url_for("static", filename=og_image_path)) if base_url else ""
    structured_data = core_structured_data(base_url, socials)
    if extra_structured_data:
        structured_data.extend(item for item in extra_structured_data if item)

    return {
        "projects": published_templates(),
        "services": SERVICES,
        "technologies": TECHNOLOGIES,
        "published_system_templates": published_templates(),
        "template_library_enabled": template_library_enabled(),
        "contact_email": current_app.config.get("CONTACT_EMAIL"),
        "socials": socials,
        "environment_label": current_app.config.get("ENVIRONMENT_LABEL", ""),
        "seo_title": seo_title or page_meta["title"],
        "meta_description": meta_description or page_meta["description"],
        "canonical_url": canonical_url,
        "public_base_url": base_url,
        "og_image_url": og_image_url,
        "og_image_alt": og_image_alt or "Key Castro custom real estate systems portfolio",
        "structured_data": structured_data,
        "robots_meta": "" if indexable else "noindex,nofollow",
        "google_site_verification": current_app.config.get("GOOGLE_SITE_VERIFICATION", ""),
        "bing_site_verification": current_app.config.get("BING_SITE_VERIFICATION", ""),
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
    # Completed reusable systems use their system-template page as the canonical public detail URL.
    # Nexus Properties has intentionally been removed from the public portfolio.
    item = get_system_template(slug)
    if item is None:
        abort(404)
    return redirect(url_for("site.system_template_detail", slug=item.slug), code=301)


@site.get("/system-templates")
def system_templates():
    templates = published_templates()
    if not templates:
        abort(404)
    return render_template(
        "system_templates.html",
        title="System Templates",
        templates=templates,
        **_common_context("system_templates"),
    )


@site.get("/system-templates/<slug>")
def system_template_detail(slug: str):
    item = get_system_template(slug)
    if item is None:
        abort(404)

    base_url = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    breadcrumb = breadcrumb_structured_data(
        base_url,
        [
            ("Home", "/"),
            ("System Templates", "/system-templates"),
            (item.name, f"/system-templates/{item.slug}"),
        ],
    )
    structured = software_template_structured_data(base_url, item)
    if breadcrumb:
        structured.append(breadcrumb)
    return render_template(
        "system_template_detail.html",
        title=item.name,
        system_template=item,
        **_common_context(
            "system_templates",
            seo_title=item.seo_title,
            meta_description=item.meta_description,
            og_image=item.og_image or None,
            og_image_alt=f"{item.name} system preview",
            extra_structured_data=structured,
        ),
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
    interest = record.get("source_title") or "General custom-system inquiry"
    request_type = record.get("source_action") or "General inquiry"
    message.set_content(
        "New website inquiry\n\n"
        f"Name: {record['name']}\n"
        f"Email: {record['email']}\n"
        f"Company: {company}\n"
        f"Interested in: {interest}\n"
        f"Request type: {request_type}\n\n"
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


_TEMPLATE_INTENTS = {
    "free-access": "Free Template Access",
    "customize": "Custom System / Customization",
}


def _requested_system_template() -> object | None:
    slug = (request.form.get("source_slug") if request.method == "POST" else request.args.get("template")) or ""
    slug = slug.strip().lower()
    return get_system_template(slug) if slug else None


def _requested_template_intent(template_interest) -> tuple[str, str, str]:
    if template_interest is None:
        return "", "", ""
    raw = (request.form.get("source_intent") if request.method == "POST" else request.args.get("intent")) or ""
    raw = raw.strip().lower()
    label = _TEMPLATE_INTENTS.get(raw, "System Template Inquiry")
    return raw if raw in _TEMPLATE_INTENTS else "", label, label


@site.route("/contact", methods=["GET", "POST"])
def contact():
    context = _common_context("contact")
    context["csrf_token"] = _csrf_token()
    template_interest = _requested_system_template()
    source_intent, source_action, source_action_label = _requested_template_intent(template_interest)
    context["template_interest"] = template_interest
    context["source_intent"] = source_intent
    context["source_action_label"] = source_action_label

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
            "source_type": "system_template" if template_interest else "",
            "source_slug": template_interest.slug if template_interest else "",
            "source_title": template_interest.name if template_interest else "",
            "source_action": source_action if template_interest else "",
        }

        mode = current_app.config.get("CONTACT_DELIVERY_MODE", "local")
        try:
            if mode == "database":
                inquiry_id = create_inquiry(record)
                current_app.logger.info("Website inquiry %s stored for %s", inquiry_id, email)
                # Email notification is optional. A failure here must never lose the stored inquiry.
                if current_app.config.get("SMTP_HOST") and current_app.config.get("SMTP_FROM_EMAIL"):
                    try:
                        _send_smtp_message(record)
                    except Exception:
                        current_app.logger.exception("Optional SMTP notification failed for inquiry %s", inquiry_id)
                flash("Project details received. I’ll review your message and reply using the email address you provided.", "success")
            elif mode == "smtp":
                _send_smtp_message(record)
                flash("Thanks. Your project details were sent successfully.", "success")
            elif current_app.config.get("ENABLE_LOCAL_CONTACT_STORAGE"):
                _store_local_message(record)
                current_app.logger.info("Local contact message stored for %s", email)
                flash("Saved locally for testing. Public delivery will use the configured business inbox.", "success")
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
    version_file = Path(current_app.root_path).parent / "VERSION.txt"
    try:
        version = version_file.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        version = "unknown"
    return jsonify(
        status="ok",
        app=current_app.config.get("APP_NAME", "Key Castro Portfolio"),
        environment=current_app.config.get("ENVIRONMENT_LABEL", "unknown"),
        version=version,
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
    templates = published_templates()
    if templates:
        pages.append(url_for("site.system_templates", _external=True))
        pages.extend(
            url_for("site.system_template_detail", slug=item.slug, _external=True) for item in templates
        )

    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += "\n".join(f"  <url><loc>{page}</loc></url>" for page in pages)
    body += "\n</urlset>"
    return current_app.response_class(body, mimetype="application/xml")


@site.app_errorhandler(400)
def bad_request(error):
    return render_template(
        "error.html",
        title="Bad Request",
        code=400,
        message="That request could not be completed.",
        **_common_context(indexable=False),
    ), 400


@site.app_errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        title="Not Found",
        code=404,
        message="The page you requested does not exist.",
        **_common_context(indexable=False),
    ), 404


@site.app_errorhandler(500)
def server_error(error):
    return render_template(
        "error.html",
        title="Server Error",
        code=500,
        message="The website encountered an unexpected error.",
        **_common_context(indexable=False),
    ), 500
