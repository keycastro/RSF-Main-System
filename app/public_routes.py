from __future__ import annotations

import hmac
import re
import secrets
from datetime import datetime, timezone
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

from .client_ops import create_public_inquiry
from .seo import (
    absolute_url,
    breadcrumb_structured_data,
    core_structured_data,
    software_template_structured_data,
)
from .system_templates import (
    EXISTING_SYSTEM_PRICING,
    MANAGED_MAINTENANCE_PRICING,
    get_system_template,
    managed_service_action_for_plan,
    published_templates,
    split_managed_service_action,
    template_library_enabled,
)

site = Blueprint("site", __name__)

SERVICES = [
    {
        "kind": "existing-system",
        "title": "Buy an existing system",
        "text": "Choose a working Realty Systems Foundry system. Changes are priced separately.",
        "example": "Changes are priced separately as upgrades.",
    },
    {
        "kind": "custom-build",
        "title": "Build a custom system",
        "text": "If none of the existing systems fits, we can build around your workflow and requirements.",
        "example": "Development and customization are quoted separately based on scope.",
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
        "title": "Custom Real Estate Systems | Realty Systems Foundry",
        "description": "Realty Systems Foundry builds custom software systems for real estate businesses. Choose an existing system or request a purpose-built system for your operation.",
    },
    "about": {
        "title": "About Realty Systems Foundry | Real Estate Technology",
        "description": "Realty Systems Foundry designs, builds, and manages custom software systems and automation for real estate businesses.",
    },
    "services": {
        "title": "Services & Pricing | Realty Systems Foundry",
        "description": "See Realty Systems Foundry services and pricing: choose an existing system or request a custom build, then choose who manages the technical side.",
    },
    "skills": {
        "title": "Technology Capabilities | Realty Systems Foundry",
        "description": "Technology capabilities used by Realty Systems Foundry to build custom real estate software systems and business workflows.",
    },
    "experience": {
        "title": "Development Experience | Realty Systems Foundry",
        "description": "Development experience focused on complete real estate systems, testing, documentation, and reliable delivery.",
    },
    "contact": {
        "title": "Contact Realty Systems Foundry | Real Estate Systems",
        "description": "Tell Realty Systems Foundry what your real estate business needs and get a reply by email.",
    },
    "system_templates": {
        "title": "Real Estate Systems | Realty Systems Foundry",
        "description": "See working Realty Systems Foundry systems for property operations, property listings, and housing workflows. Existing systems have a clear one-time price; changes are priced separately.",
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
        "services": SERVICES,
        "technologies": TECHNOLOGIES,
        "published_system_templates": published_templates(),
        "template_library_enabled": template_library_enabled(),
        "existing_system_pricing": EXISTING_SYSTEM_PRICING,
        "maintenance_pricing": MANAGED_MAINTENANCE_PRICING,
        "contact_email": current_app.config.get("CONTACT_EMAIL"),
        "socials": socials,
        "environment_label": current_app.config.get("ENVIRONMENT_LABEL", ""),
        "seo_title": seo_title or page_meta["title"],
        "meta_description": meta_description or page_meta["description"],
        "canonical_url": canonical_url,
        "public_base_url": base_url,
        "og_image_url": og_image_url,
        "og_image_alt": og_image_alt or "Realty Systems Foundry custom real estate systems",
        "structured_data": structured_data,
        "robots_meta": "" if indexable else "noindex,nofollow",
        "google_site_verification": current_app.config.get("GOOGLE_SITE_VERIFICATION", ""),
        "bing_site_verification": current_app.config.get("BING_SITE_VERIFICATION", ""),
    }


@site.get("/")
def home():
    return render_template("public/home.html", title="Custom Real Estate Systems", **_common_context("home"))


@site.get("/about")
def about():
    return render_template("public/about.html", title="About", **_common_context("about"))


@site.get("/services")
def services():
    return render_template("public/services.html", title="Services & Pricing", **_common_context("services"))


@site.get("/projects")
def projects():
    # Projects and System Templates described the same two completed systems in 2.8.0.
    # Keep the legacy URL for inbound links, but use one public mental model: Systems.
    return redirect(url_for("site.system_templates"), code=301)


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
        "public/system_templates.html",
        title="Systems",
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
            ("Systems", "/system-templates"),
            (item.name, f"/system-templates/{item.slug}"),
        ],
    )
    structured = software_template_structured_data(base_url, item)
    if breadcrumb:
        structured.append(breadcrumb)
    return render_template(
        "public/system_template_detail.html",
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
    # Skills are now summarized on About to keep the public site simple.
    return redirect(url_for("site.about"), code=301)


@site.get("/experience")
def experience():
    # Experience is now summarized on About to avoid a second credibility page.
    return redirect(url_for("site.about"), code=301)


def _csrf_token():
    token = session.get("contact_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["contact_csrf"] = token
    return token


def _valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))


_TEMPLATE_INTENTS = {
    "existing-system": ("existing-system", "Existing System Purchase"),
    "customize": ("customize", "Customize Existing System"),
    "custom-build": ("custom-build", "Custom System Build"),
    "handover": ("handover", "Full Handover"),
    "managed": ("managed", "Managed by Realty Systems Foundry"),
    # Backward compatibility for old public links from the retired access/subscription models.
    "subscribe": ("managed", "Managed by Realty Systems Foundry"),
    "free-access": ("managed", "Managed by Realty Systems Foundry"),
}


def _requested_system_template() -> object | None:
    slug = (request.form.get("source_slug") if request.method == "POST" else request.args.get("template")) or ""
    slug = slug.strip().lower()
    return get_system_template(slug) if slug else None


def _requested_intent(template_interest) -> tuple[str, str, str]:
    raw = (request.form.get("source_intent") if request.method == "POST" else request.args.get("intent")) or ""
    raw = raw.strip().lower()
    canonical_intent, label = _TEMPLATE_INTENTS.get(raw, ("", ""))
    if not canonical_intent:
        return "", "", ""
    # System purchase/customization may point to a selected system. Keep legacy
    # customization links readable, but never trust browser-supplied titles or prices.
    return canonical_intent, label, label


def _requested_maintenance_plan(source_intent: str):
    if source_intent != "managed":
        return None
    raw = (request.form.get("source_plan") if request.method == "POST" else request.args.get("plan")) or ""
    return MANAGED_MAINTENANCE_PRICING.get_plan(raw)


@site.route("/contact", methods=["GET", "POST"])
def contact():
    context = _common_context("contact")
    context["csrf_token"] = _csrf_token()
    template_interest = _requested_system_template()
    source_intent, source_action, source_action_label = _requested_intent(template_interest)
    selected_maintenance_plan = _requested_maintenance_plan(source_intent)
    if source_intent == "managed":
        source_action = managed_service_action_for_plan(selected_maintenance_plan)
    context["template_interest"] = template_interest
    context["source_intent"] = source_intent
    context["source_action_label"] = source_action_label
    context["selected_maintenance_plan"] = selected_maintenance_plan

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
            return render_template("public/contact.html", title="Contact", **context), 400

        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "email": email,
            "company": company,
            "message": message,
            "source_type": "system_template" if template_interest else ("service" if source_intent else ""),
            "source_slug": template_interest.slug if template_interest else "",
            "source_title": template_interest.name if template_interest else ("Realty Systems Foundry Services" if source_intent else ""),
            "source_action": source_action if source_intent else "",
        }

        try:
            inquiry_id = create_public_inquiry(record)
            current_app.logger.info("Website inquiry %s stored for %s", inquiry_id, email)
            flash("Message received. We’ll reply by email.", "success")
        except Exception:
            current_app.logger.exception("Contact delivery failed")
            flash("Your message could not be sent right now. Please try again later.", "error")
            context["form_data"] = {"name": name, "email": email, "company": company, "message": message}
            return render_template("public/contact.html", title="Contact", **context), 503

        session["contact_csrf"] = secrets.token_urlsafe(32)
        return redirect(url_for("site.contact"))

    return render_template("public/contact.html", title="Contact", **context)


@site.get("/system/health")
def health():
    version_file = Path(current_app.root_path).parent / "VERSION.txt"
    try:
        version = version_file.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        version = "unknown"
    return jsonify(
        status="ok",
        app=current_app.config.get("APP_NAME", "Realty Systems Foundry"),
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
    pages = [url_for("site.home", _external=True)]
    templates = published_templates()
    if templates:
        pages.append(url_for("site.system_templates", _external=True))
        pages.extend(
            url_for("site.system_template_detail", slug=item.slug, _external=True) for item in templates
        )
    pages.extend(
        [
            url_for("site.services", _external=True),
            url_for("site.about", _external=True),
            url_for("site.contact", _external=True),
        ]
    )

    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += "\n".join(f"  <url><loc>{page}</loc></url>" for page in pages)
    body += "\n</urlset>"
    return current_app.response_class(body, mimetype="application/xml")


@site.errorhandler(400)
def bad_request(error):
    return render_template(
        "public/error_public.html",
        title="Bad Request",
        code=400,
        message="That request could not be completed.",
        **_common_context(indexable=False),
    ), 400


@site.errorhandler(404)
def not_found(error):
    return render_template(
        "public/error_public.html",
        title="Not Found",
        code=404,
        message="The page you requested does not exist.",
        **_common_context(indexable=False),
    ), 404


@site.errorhandler(500)
def server_error(error):
    return render_template(
        "public/error_public.html",
        title="Server Error",
        code=500,
        message="The website encountered an unexpected error.",
        **_common_context(indexable=False),
    ), 500
