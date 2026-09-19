from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

TemplateStatus = Literal["draft", "published"]
SubscriptionPlanKey = Literal["monthly", "yearly"]
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class SubscriptionPlan:
    key: SubscriptionPlanKey
    label: str
    amount: int
    interval: str
    currency_symbol: str

    @property
    def price_label(self) -> str:
        return f"{self.currency_symbol}{self.amount}/{self.interval}"


@dataclass(frozen=True)
class ManagedSubscriptionPricing:
    """Single trusted pricing source for every published ready-made system."""

    currency_code: str = "USD"
    currency_symbol: str = "$"
    monthly_price: int = 49
    yearly_price: int = 490

    @property
    def annual_monthly_total(self) -> int:
        return self.monthly_price * 12

    @property
    def annual_savings(self) -> int:
        return self.annual_monthly_total - self.yearly_price

    @property
    def monthly(self) -> SubscriptionPlan:
        return SubscriptionPlan("monthly", "Monthly", self.monthly_price, "month", self.currency_symbol)

    @property
    def yearly(self) -> SubscriptionPlan:
        return SubscriptionPlan("yearly", "Yearly", self.yearly_price, "year", self.currency_symbol)

    def get_plan(self, key: str) -> SubscriptionPlan | None:
        normalized = (key or "").strip().lower()
        if normalized == "monthly":
            return self.monthly
        if normalized == "yearly":
            return self.yearly
        return None


MANAGED_SUBSCRIPTION_PRICING = ManagedSubscriptionPricing()
_SUBSCRIPTION_ACTION_PREFIX = "System Subscription — "


def subscription_action_for_plan(plan: SubscriptionPlan | None) -> str:
    if plan is None:
        return "System Subscription"
    return f"{_SUBSCRIPTION_ACTION_PREFIX}{plan.label} · {plan.price_label}"


def split_subscription_action(value: str) -> tuple[str, str]:
    """Return a stable request label plus an optional historical plan label."""
    action = (value or "").strip()
    if action.startswith(_SUBSCRIPTION_ACTION_PREFIX):
        return "System Subscription", action[len(_SUBSCRIPTION_ACTION_PREFIX) :]
    return action, ""


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
        short_description="Track property work, deadlines, follow-ups, approvals, rentals, and team tasks in one place.",
        card_audience="Property managers, rental teams, and operations teams.",
        full_description="Manage daily property work, deadlines, follow-ups, approvals, rentals, and team tasks in one place.",
        business_problem=(
            "Property work is easy to miss when tasks, deadlines, approvals, and updates are spread across chats "
            "and separate tools. This system keeps the important work in one place."
        ),
        target_users=(
            "Property managers",
            "Rental and short-term rental teams",
            "Property operations teams",
        ),
        workflow=(
            "Add properties, contacts, and work.",
            "Assign tasks, priorities, due dates, and follow-up dates.",
            "Use the dashboard to see urgent work, approvals, and rental readiness.",
            "Track completed work and activity history.",
        ),
        features=(
            "Roles for Owner/Admin, Operations, and Team Member users",
            "Dashboard for urgent, overdue, and follow-up work",
            "Task tracking with priority, deadline, assignment, and status",
            "Owner approvals",
            "Rental booking, guest readiness, contractor, and turnover tracking",
            "Tenant placement and reusable checklists",
            "Automatic alerts and turnover tasks",
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
            "The standard system shown on this page",
            "Standard roles, property records, task tracking, approvals, rentals, and checklists",
            "Standard alerts and tasks after checkout",
            "Hosting, setup, and support details are confirmed before access starts",
            "Payment processing, accounting, AI, e-signing, and a native mobile app are not included in the standard system",
        ),
        customization_opportunities=(
            "Company branding and wording",
            "Different roles, permissions, and approval rules",
            "Custom fields, reports, work steps, alerts, or connections to other tools",
            "Extra modules for your property process",
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
                caption="Dashboard using sample data — urgent work, due tasks, arrivals, and owner decisions.",
            ),
            TemplateScreenshot(
                src="images/templates/property-operations-command-center/work.png",
                alt="Property Operations Command Center work queue interface preview using sample data",
                caption="Work list using sample data — priority, status, due date, follow-up, and assigned person.",
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
        short_description="Keep private property listings in one searchable place and keep them up to date.",
        card_audience="Brokerages and real estate teams sharing private listings.",
        full_description="A private system for teams to add, search, update, and manage shared property listings.",
        business_problem=(
            "Listings become hard to trust when they are spread across chats, spreadsheets, and agent files. "
            "This system keeps shared inventory searchable and shows when listings need to be checked or updated."
        ),
        target_users=(
            "Real estate brokerages",
            "Sales and leasing teams",
            "Teams sharing private or off-market listings",
        ),
        workflow=(
            "Authorized users sign in.",
            "Agents add and update property listings.",
            "The team searches and filters shared inventory.",
            "Old or unavailable listings move to history instead of disappearing.",
        ),
        features=(
            "Administrator and Agent roles",
            "Searchable shared property inventory",
            "Filters for property type, sale or rent, availability, price, bedrooms, and sorting",
            "My Listings for each agent",
            "Reconfirmation and automatic expiry for old listings",
            "Withdraw, archive, restore, and history tools",
            "User, access-code, freshness, and branding settings",
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
            "The standard system shown on this page",
            "Administrator and Agent access",
            "Dashboard, shared listings, My Listings, History, and Management",
            "Standard search, filters, listing ownership, checks for old listings, archive, and restore tools",
            "Hosting, setup, and support details are confirmed before access starts",
        ),
        customization_opportunities=(
            "Company branding and property fields",
            "Different roles, teams, permissions, or approval steps",
            "Custom reports, alerts, exports, or connections to other tools",
            "Extra modules for your listing workflow",
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
                caption="Dashboard using sample data — current listings and listings that need attention.",
            ),
            TemplateScreenshot(
                src="images/templates/property-inventory-hub/marketplace.png",
                alt="Property Inventory Hub marketplace interface preview using sample data",
                caption="Marketplace using sample data — search, filters, availability, and listing status.",
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
