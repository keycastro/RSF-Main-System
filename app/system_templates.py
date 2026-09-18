from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

TemplateStatus = Literal["draft", "published"]
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class TemplateScreenshot:
    src: str
    alt: str
    caption: str


@dataclass(frozen=True)
class VideoDemo:
    url: str = ""
    embed_url: str = ""
    thumbnail: str = ""
    name: str = ""
    description: str = ""
    upload_date: str = ""
    transcript: str = ""


@dataclass(frozen=True)
class SystemTemplate:
    """Source-controlled metadata for one reusable business-system template.

    Keep entries in ``SYSTEM_TEMPLATES`` as ``draft`` until the system, written
    content, media, managed-subscription scope, CTA flow, SEO metadata, and
    security review are all ready. Draft entries never become public routes or
    sitemap entries.
    """

    slug: str
    name: str
    category: str
    short_description: str
    card_audience: str
    full_description: str
    business_problem: str
    target_users: tuple[str, ...]
    workflow: tuple[str, ...]
    features: tuple[str, ...]
    technologies: tuple[str, ...]
    standard_scope: tuple[str, ...]
    customization_opportunities: tuple[str, ...]
    search_terms: tuple[str, ...] = field(default_factory=tuple)
    status: TemplateStatus = "draft"
    screenshots: tuple[TemplateScreenshot, ...] = field(default_factory=tuple)
    video: VideoDemo = field(default_factory=VideoDemo)
    project_note: str = ""
    seo_title: str = ""
    meta_description: str = ""
    og_image: str = ""
    published_date: str = ""
    updated_date: str = ""

    @property
    def search_text(self) -> str:
        """Plain-text search document used by the client-side Systems filter.

        Keep search behavior metadata-driven: future published systems become
        searchable automatically when their normal metadata and optional
        ``search_terms`` are added to this registry.
        """
        parts = (
            self.name,
            self.category,
            self.short_description,
            self.card_audience,
            self.business_problem,
            *self.target_users,
            *self.search_terms,
        )
        return " ".join(part.strip() for part in parts if part and part.strip())

    def __post_init__(self) -> None:
        if not _SLUG_PATTERN.fullmatch(self.slug):
            raise ValueError(f"Invalid system-template slug: {self.slug!r}")
        if self.status not in {"draft", "published"}:
            raise ValueError(f"Invalid system-template status: {self.status!r}")
        if self.status == "published":
            required = {
                "name": self.name,
                "category": self.category,
                "short_description": self.short_description,
                "card_audience": self.card_audience,
                "full_description": self.full_description,
                "business_problem": self.business_problem,
                "seo_title": self.seo_title,
                "meta_description": self.meta_description,
            }
            missing = [key for key, value in required.items() if not value.strip()]
            if missing:
                raise ValueError(
                    "Published system template is missing required fields: " + ", ".join(missing)
                )


SYSTEM_TEMPLATES: tuple[SystemTemplate, ...] = (
    SystemTemplate(
        slug="property-operations-command-center",
        name="Property Operations Command Center",
        category="Property Operations",
        short_description=(
            "An action-first operations system for property teams to track work, deadlines, "
            "follow-ups, approvals, guest readiness, tenant placement, and repeatable SOPs."
        ),
        card_audience="Property managers, rental operators, and property-operations teams.",
        full_description=(
            "A completed property-operations application built around one practical goal: know what "
            "needs attention before something gets missed. It brings day-to-day operational work, "
            "follow-ups, approvals, readiness, and repeatable processes into one structured workspace."
        ),
        business_problem=(
            "Property operations can scatter deadlines, follow-ups, guest-readiness tasks, contractor "
            "coordination, owner decisions, tenant-placement stages, and checklists across messages and "
            "separate tools. This system brings those operational attention points into one structured workspace."
        ),
        target_users=(
            "Property operations owners and managers",
            "Short-term rental operations teams",
            "Rental and tenant-placement teams",
            "Operations coordinators managing deadlines, contractors, and approvals",
        ),
        workflow=(
            "Record the properties, contacts, and operational records the team is responsible for.",
            "Create work items with a type, priority, due date, follow-up date, assignment, and status.",
            "Use the operations dashboard to surface overdue, urgent, waiting-owner, and follow-up work.",
            "Coordinate short-term-rental bookings, guest readiness, tenant-placement stages, and reusable checklists.",
            "Route decisions through the owner-approval queue when work is blocked by an owner decision.",
            "Run rule-based automation for overdue work, same-day readiness alerts, and post-checkout turnover work.",
            "Use activity history and operational reports to keep actions and completed work visible.",
        ),
        features=(
            "Role-based access for Owner/Admin, Operations, and Team Member users",
            "Action-oriented dashboard with due today, overdue, follow-up, owner-waiting, issue, and arrival counts",
            "Work items with priority, deadlines, follow-ups, blockers, assignments, and completion tracking",
            "Owner approval requests with auditable decisions and escalation behavior",
            "Short-term-rental booking, arrival-readiness, cleaner/contractor coordination, and turnover tracking",
            "Tenant-placement pipeline from inquiry through placement stages",
            "Reusable checklist and SOP templates with checklist instances",
            "Rule-based automation for overdue items, guest-readiness alerts, and turnover tasks/checklists",
            "Property and external-contact records, activity history, reports, and external document links",
        ),
        technologies=(
            "Python",
            "Flask",
            "SQLAlchemy",
            "SQLite",
            "Server-rendered HTML/CSS/JavaScript",
            "Waitress for local Windows runtime",
        ),
        standard_scope=(
            "The complete standard workflow shown on this page",
            "Owner/Admin, Operations, and Team Member role model",
            "Properties, contacts, work tracking, approvals, short-term-rental operations, tenant placement, and checklists",
            "Rule-based attention and turnover automation included in the standard build",
            "Managed access to the standard system; hosting, database, onboarding, and support details are confirmed before subscription activation",
            "No payment processing, accounting, external property-platform integrations, AI assistant, e-signing, or native mobile app in the standard build",
        ),
        customization_opportunities=(
            "Company branding and terminology",
            "Different roles, permissions, approval rules, and operational statuses",
            "Business-specific dashboards, reports, fields, and workflow stages",
            "Custom automation and notification rules",
            "Database, hosting, deployment, or multi-user environment changes",
            "Integrations with approved external systems or APIs",
            "Additional modules built around the company’s actual property-operation process",
        ),
        search_terms=(
            "property management",
            "property operations",
            "operations",
            "rental",
            "maintenance",
            "tenant",
            "workflow",
            "approvals",
            "guest readiness",
            "short-term rental",
            "SOP",
            "checklist",
            "follow-up",
            "contractor",
        ),
        status="published",
        screenshots=(
            TemplateScreenshot(
                src="images/templates/property-operations-command-center/dashboard.png",
                alt="Property Operations Command Center dashboard interface preview using sample data",
                caption="Operations dashboard interface preview using sample data — attention queue, due work, arrivals, and owner decisions.",
            ),
            TemplateScreenshot(
                src="images/templates/property-operations-command-center/work.png",
                alt="Property Operations Command Center work queue interface preview using sample data",
                caption="Work queue interface preview using sample data — priority, status, due date, follow-up, and assignment tracking.",
            ),
        ),
        project_note=(
            "Completed independent implementation developed by Key Castro and offered through managed "
            "system subscription access. It is not presented as commissioned or adopted client software."
        ),
        seo_title="Property Operations Command Center | Key Castro",
        meta_description=(
            "Explore Property Operations Command Center by Key Castro: a managed property-operations system for work, deadlines, approvals, guest readiness, tenant placement, SOPs, and automation."
        ),
        og_image="images/templates/property-operations-command-center/dashboard.png",
        published_date="2026-09-19",
        updated_date="2026-09-19",
    ),
    SystemTemplate(
        slug="property-inventory-hub",
        name="Property Inventory Hub",
        category="Real Estate Inventory",
        short_description=(
            "A private property-inventory workspace where authorized real-estate teams can add, search, "
            "maintain, reconfirm, and retire shared off-market listings."
        ),
        card_audience="Brokerages and real-estate teams managing shared private inventory.",
        full_description=(
            "A completed, brand-neutral internal real-estate inventory system for teams that need one private "
            "place to keep shared property listings searchable, owned, reconfirmed, and current."
        ),
        business_problem=(
            "Shared property inventory becomes difficult to trust when listings live in chats, spreadsheets, or "
            "separate agent files. Availability gets stale, ownership is unclear, and useful older records are "
            "hard to find. Property Inventory Hub centralizes the private marketplace and adds a freshness lifecycle."
        ),
        target_users=(
            "Real-estate brokerages managing shared private inventory",
            "Sales and leasing teams working with off-market properties",
            "Property teams that need searchable internal inventory",
            "Administrators who need control over authorized users, freshness rules, and client branding",
        ),
        workflow=(
            "Authorized users sign in with a private access code.",
            "Agents add property records with location, type, sale/rent purpose, price, and relevant property details.",
            "The team searches and filters the shared Marketplace to find current inventory.",
            "Each agent maintains the current listings they are responsible for in My Listings.",
            "Freshness rules calculate reconfirmation and expiry dates so availability is reviewed before listings become stale.",
            "Expired, unavailable, or archived records move into History instead of disappearing.",
            "Administrators manage users, access codes, freshness rules, and deployment branding from Management.",
        ),
        features=(
            "Secure access-code sign-in with Administrator and Agent roles",
            "Shared Marketplace with text search, property type, sale/rent, availability, price, bedroom, and sorting filters",
            "Property records for location, type, purpose, price, bedrooms, bathrooms, size, furnishing, parking, and agent notes",
            "My Listings view for current properties owned by the signed-in agent",
            "Freshness engine with reconfirmation dates, expiry dates, automatic due state, and automatic expiry",
            "Manual reconfirmation, withdrawal, archive, and restore workflows",
            "Listing status history and reconfirmation history",
            "History view for expired, unavailable, and historical records",
            "Management tools for authorized users, access codes, freshness rules, and client branding",
            "Configurable company name, app title, logo, colors, business email, and phone without rebuilding the app",
        ),
        technologies=(
            "Python",
            "Flask",
            "SQLAlchemy",
            "SQLite",
            "Flask-Login and Flask-WTF",
            "Server-rendered HTML/CSS/JavaScript",
        ),
        standard_scope=(
            "Brand-neutral Property Inventory Hub workspace",
            "Administrator and Agent access model",
            "Dashboard, Marketplace, My Listings, History, and Management areas",
            "Standard property fields, search/filter tools, and listing ownership workflow",
            "Freshness, reconfirmation, expiry, withdrawal, archive, and restore lifecycle",
            "Configurable client branding in the standard application",
            "Managed access to the standard system; hosting, database, onboarding, and support details are confirmed before subscription activation",
        ),
        customization_opportunities=(
            "Company-specific property fields, listing types, statuses, and business rules",
            "Different user roles, permissions, teams, branches, or approval processes",
            "Custom dashboards, reports, analytics, exports, or notifications",
            "Alternative database and hosted deployment architecture",
            "Integrations with approved CRM, listing, messaging, or property systems",
            "Additional modules around the brokerage’s own inventory and agent workflow",
        ),
        search_terms=(
            "inventory",
            "property inventory",
            "brokerage",
            "listings",
            "off-market listings",
            "marketplace",
            "agents",
            "reconfirmation",
            "property search",
            "sales",
            "leasing",
            "listing management",
        ),
        status="published",
        screenshots=(
            TemplateScreenshot(
                src="images/templates/property-inventory-hub/dashboard.png",
                alt="Property Inventory Hub dashboard interface preview using sample data",
                caption="Dashboard interface preview using sample data — current inventory, personal inventory, and listings needing attention.",
            ),
            TemplateScreenshot(
                src="images/templates/property-inventory-hub/marketplace.png",
                alt="Property Inventory Hub marketplace interface preview using sample data",
                caption="Marketplace interface preview using sample data — searchable inventory, filters, availability, and reconfirmation status.",
            ),
        ),
        project_note=(
            "Completed reusable system developed by Key Castro and offered through managed system subscription "
            "access. Client branding is configurable; no claim is made that a specific company commissioned or adopted it."
        ),
        seo_title="Property Inventory Hub | Key Castro",
        meta_description=(
            "Explore Property Inventory Hub by Key Castro: a managed private real-estate inventory system with search, listing ownership, reconfirmation, expiry, history, and configurable branding."
        ),
        og_image="images/templates/property-inventory-hub/dashboard.png",
        published_date="2026-09-19",
        updated_date="2026-09-19",
    ),
)


def published_templates() -> tuple[SystemTemplate, ...]:
    return tuple(item for item in SYSTEM_TEMPLATES if item.status == "published")


def get_system_template(slug: str, *, include_drafts: bool = False) -> SystemTemplate | None:
    for item in SYSTEM_TEMPLATES:
        if item.slug == slug and (include_drafts or item.status == "published"):
            return item
    return None


def template_library_enabled() -> bool:
    return bool(published_templates())
