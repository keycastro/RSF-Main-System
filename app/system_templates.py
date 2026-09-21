from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

TemplateStatus = Literal["draft", "published"]
MaintenancePlanKey = Literal["monthly", "yearly"]
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class MaintenancePlan:
    key: MaintenancePlanKey
    label: str
    amount: int
    interval: str
    currency_symbol: str

    @property
    def price_label(self) -> str:
        return f"{self.currency_symbol}{self.amount}/{self.interval}"


@dataclass(frozen=True)
class ExistingSystemPricing:
    """Single trusted price for every published existing system."""

    currency_code: str = "USD"
    currency_symbol: str = "$"
    one_time_price: int = 199

    @property
    def price_label(self) -> str:
        return f"{self.currency_symbol}{self.one_time_price}"

    @property
    def one_time_label(self) -> str:
        return f"{self.price_label} one-time"


EXISTING_SYSTEM_PRICING = ExistingSystemPricing()


@dataclass(frozen=True)
class ManagedMaintenancePricing:
    """Single trusted pricing source for optional managed maintenance."""

    currency_code: str = "USD"
    currency_symbol: str = "$"
    monthly_price: int = 39
    yearly_price: int = 390

    @property
    def annual_monthly_total(self) -> int:
        return self.monthly_price * 12

    @property
    def annual_savings(self) -> int:
        return self.annual_monthly_total - self.yearly_price

    @property
    def monthly(self) -> MaintenancePlan:
        return MaintenancePlan("monthly", "Monthly", self.monthly_price, "month", self.currency_symbol)

    @property
    def yearly(self) -> MaintenancePlan:
        return MaintenancePlan("yearly", "Yearly", self.yearly_price, "year", self.currency_symbol)

    def get_plan(self, key: str) -> MaintenancePlan | None:
        normalized = (key or "").strip().lower()
        if normalized == "monthly":
            return self.monthly
        if normalized == "yearly":
            return self.yearly
        return None


MANAGED_MAINTENANCE_PRICING = ManagedMaintenancePricing()
_MANAGED_SERVICE_ACTION_PREFIX = "Managed by Realty Systems Foundry — "
_LEGACY_KEY_CASTRO_MANAGED_PREFIX = "Managed by KEY CASTRO — "
_LEGACY_SUBSCRIPTION_ACTION_PREFIX = "System Subscription — "


def managed_service_action_for_plan(plan: MaintenancePlan | None) -> str:
    if plan is None:
        return "Managed by Realty Systems Foundry"
    return f"{_MANAGED_SERVICE_ACTION_PREFIX}{plan.label} · {plan.price_label}"


def split_managed_service_action(value: str) -> tuple[str, str]:
    """Return the current request label plus an optional plan label.

    Older stored subscription labels are normalized for display so historical
    inquiries remain readable after the 3.6.0 business-model change.
    """
    action = (value or "").strip()
    if action.startswith(_MANAGED_SERVICE_ACTION_PREFIX):
        return "Managed by Realty Systems Foundry", action[len(_MANAGED_SERVICE_ACTION_PREFIX) :]
    if action.startswith(_LEGACY_KEY_CASTRO_MANAGED_PREFIX):
        return "Managed by Realty Systems Foundry", action[len(_LEGACY_KEY_CASTRO_MANAGED_PREFIX) :]
    if action.startswith(_LEGACY_SUBSCRIPTION_ACTION_PREFIX):
        return "Managed by Realty Systems Foundry", action[len(_LEGACY_SUBSCRIPTION_ACTION_PREFIX) :]
    if action in {"Managed by KEY CASTRO", "System Subscription"}:
        return "Managed by Realty Systems Foundry", ""
    if action == "Paid Customization":
        return "Customize Existing System", ""
    return action, ""


# Backward-compatible names for old internal imports or local tools. Public code
# uses the managed-maintenance terminology above.
SubscriptionPlanKey = MaintenancePlanKey
SubscriptionPlan = MaintenancePlan
ManagedSubscriptionPricing = ManagedMaintenancePricing
MANAGED_SUBSCRIPTION_PRICING = MANAGED_MAINTENANCE_PRICING
subscription_action_for_plan = managed_service_action_for_plan
split_subscription_action = split_managed_service_action


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
    """Source-controlled metadata for one reusable business system.

    Keep entries in ``SYSTEM_TEMPLATES`` as ``draft`` until the system, written
    content, media, customization scope, delivery/management choices, CTA flow,
    SEO metadata, and security review are ready. Draft entries never become
    public routes or sitemap entries.
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
    managed_scope: tuple[str, ...]
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


_COMMON_MANAGED_SCOPE = (
    "Hosting and deployment management",
    "Routine backups and technical maintenance",
    "Technical fixes for the current system",
    "Technical support within the agreed service scope",
    "New features, workflow changes, and other upgrades are priced separately",
)


SYSTEM_TEMPLATES: tuple[SystemTemplate, ...] = (
    SystemTemplate(
        slug="property-operations-command-center",
        name="Property Operations Command Center",
        category="Property Operations",
        short_description="Keep property tasks, deadlines, approvals, rentals, and follow-ups together in one place.",
        card_audience="Property managers and teams handling daily property work.",
        full_description="Keep daily property work, deadlines, approvals, rentals, and team tasks organized in one place.",
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
            "Add the properties, people, and work your team needs to track.",
            "Give tasks to team members and set due dates.",
            "See urgent work, approvals, and rental updates on one main screen.",
            "Keep a record of completed work and past activity.",
        ),
        features=(
            "Different access for owners, managers, and team members",
            "See urgent, overdue, and follow-up work in one place",
            "Track who is doing each task and when it is due",
            "Ask owners for approval when needed",
            "Track rentals, guest preparation, contractors, and turnovers",
            "Track tenant placement and use repeatable checklists",
            "Get reminders for important work and turnovers",
        ),
        technologies=(
            "Python",
            "Flask",
            "SQLAlchemy",
            "SQLite",
            "Server-rendered HTML/CSS/JavaScript",
            "Waitress for local Windows runtime",
        ),
        managed_scope=_COMMON_MANAGED_SCOPE,
        customization_opportunities=(
            "Your company name, colors, and wording",
            "Who can see, change, or approve information",
            "The information, reports, steps, and reminders your team needs",
            "Extra parts needed for your property work",
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
                alt="Property Operations Command Center main screen preview using sample data",
                caption="Main screen using sample data — urgent work, due tasks, arrivals, and owner decisions.",
            ),
            TemplateScreenshot(
                src="images/templates/property-operations-command-center/work.png",
                alt="Property Operations Command Center work queue interface preview using sample data",
                caption="Work list using sample data — priority, status, due date, follow-up, and assigned person.",
            ),
        ),
        project_note=(
            "Independent system from Realty Systems Foundry, founded by Key Castro. It is not presented as software commissioned or used by a specific client."
        ),
        seo_title="Property Operations Command Center | Realty Systems Foundry",
        meta_description=(
            "Explore Property Operations Command Center by Realty Systems Foundry: a customizable property-operations system "
            "for work, deadlines, approvals, guest readiness, tenant placement, SOPs, and automation."
        ),
        og_image="images/templates/property-operations-command-center/dashboard.png",
        published_date="2026-09-19",
        updated_date="2026-09-19",
    ),
    SystemTemplate(
        slug="property-inventory-hub",
        name="Property Inventory Hub",
        category="Real Estate Inventory",
        short_description="Keep property listings in one place so your team can find and update them easily.",
        card_audience="Real estate teams that share property listings.",
        full_description="Keep your property listings organized and easy for your team to search and update.",
        business_problem=(
            "Property listings are hard to manage when they are spread across chats, spreadsheets, and different files. "
            "This system keeps them together so your team can find and update them easily."
        ),
        target_users=(
            "Real estate brokerages",
            "Sales and leasing teams",
            "Teams sharing private or off-market listings",
        ),
        workflow=(
            "Your team signs in.",
            "Add or update a property listing.",
            "Search for the property you need.",
            "Move old or unavailable listings to history instead of deleting them.",
        ),
        features=(
            "Different access for admins and agents",
            "Search all team property listings in one place",
            "Find properties by type, price, bedrooms, availability, and more",
            "Each agent can quickly see their own listings",
            "Reminders to check old listings",
            "Keep old listings in history and bring them back when needed",
            "Manage team access, listing checks, and your company name and look",
        ),
        technologies=(
            "Python",
            "Flask",
            "SQLAlchemy",
            "SQLite",
            "Flask-Login and Flask-WTF",
            "Server-rendered HTML/CSS/JavaScript",
        ),
        managed_scope=_COMMON_MANAGED_SCOPE,
        customization_opportunities=(
            "Your company name, colors, and property information",
            "Who can see or change information",
            "Reports, reminders, downloads, or connections your team needs",
            "Extra parts needed for your listing process",
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
                alt="Property Inventory Hub main screen preview using sample data",
                caption="Main screen using sample data — current listings and listings that need attention.",
            ),
            TemplateScreenshot(
                src="images/templates/property-inventory-hub/marketplace.png",
                alt="Property Inventory Hub marketplace interface preview using sample data",
                caption="Marketplace using sample data — search, filters, availability, and listing status.",
            ),
        ),
        project_note=(
            "Independent system from Realty Systems Foundry, founded by Key Castro. It is not presented as software commissioned or used by a specific client."
        ),
        seo_title="Property Inventory Hub | Realty Systems Foundry",
        meta_description=(
            "Explore Property Inventory Hub by Realty Systems Foundry: a customizable private real-estate inventory system "
            "with search, listing ownership, reconfirmation, expiry, history, and configurable branding."
        ),
        og_image="images/templates/property-inventory-hub/dashboard.png",
        published_date="2026-09-19",
        updated_date="2026-09-19",
    ),
    SystemTemplate(
        slug="student-housing-matching-and-placement-system",
        name="Student Housing Matching and Placement System",
        category="Student Housing Operations",
        short_description=(
            "Keep student housing requests, available units, viewings, reservations, and placements in one place."
        ),
        card_audience="Teams helping students find and secure housing.",
        full_description=(
            "Help your team manage student housing requests, available units, viewings, reservations, and completed placements in one place."
        ),
        business_problem=(
            "Student housing becomes hard to manage when requests, available units, viewings, and follow-ups are kept in different places. "
            "This system keeps those steps together from the first request to the final placement."
        ),
        target_users=(
            "Student housing businesses",
            "Housing coordinators and placement teams",
            "Off-campus housing and leasing teams",
        ),
        workflow=(
            "Add the student and what kind of housing they need.",
            "See available units that match the student’s needs.",
            "Review the options and schedule a viewing when needed.",
            "Keep track of follow-ups and what needs to happen next.",
            "Reserve the chosen unit and avoid double booking.",
            "Mark the student as placed and update unit availability.",
        ),
        features=(
            "Keep student details and housing requests together",
            "Track property owners, properties, units, and availability",
            "Find suitable units using clear housing requirements",
            "Track viewings and follow-ups",
            "Reserve units and help prevent double booking",
            "Different access for administrators and housing coordinators",
            "See recent activity and important updates on the main screen",
        ),
        technologies=(
            "Python",
            "Flask",
            "SQLite",
            "Server-rendered HTML/CSS/JavaScript",
            "Waitress for local Windows runtime",
        ),
        managed_scope=_COMMON_MANAGED_SCOPE,
        customization_opportunities=(
            "Your business name, colors, and wording",
            "The housing information and the way your team chooses suitable housing",
            "Who can access what, plus the main screens and reports you need",
            "The property, placement, and follow-up steps your team uses",
        ),
        search_terms=(
            "student housing",
            "housing placement",
            "student accommodation",
            "housing requests",
            "availability",
            "matching",
            "viewings",
            "follow-ups",
            "reservations",
            "placements",
            "housing coordinator",
            "off-campus housing",
        ),
        status="published",
        screenshots=(
            TemplateScreenshot(
                src="images/templates/student-housing-matching-and-placement-system/dashboard.png",
                alt="Student Housing Matching and Placement System main screen preview using synthetic sample data",
                caption="Main screen using synthetic sample data — open requests, available units, follow-ups, viewings, reservations, and placements.",
            ),
            TemplateScreenshot(
                src="images/templates/student-housing-matching-and-placement-system/match-center.png",
                alt="Student Housing Matching and Placement System Find Housing screen using synthetic sample data",
                caption="Find Housing using synthetic sample data — requests, matching status, budget, location, and move-in timing.",
            ),
        ),
        project_note=(
            "Independent portfolio project from Realty Systems Foundry, founded by Key Castro, after studying a publicly visible 2026 student-housing "
            "system request and how the housing placement process works. Not commissioned by, affiliated with, or endorsed by "
            "the original poster."
        ),
        seo_title="Student Housing Matching & Placement System | Realty Systems Foundry",
        meta_description=(
            "Explore Realty Systems Foundry's Student Housing Matching and Placement System for housing requests, availability, "
            "matching, viewings, follow-ups, reservations, and placements."
        ),
        og_image="images/templates/student-housing-matching-and-placement-system/dashboard.png",
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
