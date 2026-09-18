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
    content, media, free-standard scope, CTA flow, SEO metadata, and security
    review are all ready. Draft entries never become public routes or sitemap
    entries.
    """

    slug: str
    name: str
    category: str
    short_description: str
    full_description: str
    business_problem: str
    target_users: tuple[str, ...]
    workflow: tuple[str, ...]
    features: tuple[str, ...]
    technologies: tuple[str, ...]
    standard_scope: tuple[str, ...]
    customization_opportunities: tuple[str, ...]
    status: TemplateStatus = "draft"
    screenshots: tuple[TemplateScreenshot, ...] = field(default_factory=tuple)
    video: VideoDemo = field(default_factory=VideoDemo)
    seo_title: str = ""
    meta_description: str = ""
    og_image: str = ""
    published_date: str = ""
    updated_date: str = ""

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


# Intentionally empty in the 2.7.0 foundation release.
# Do not publish placeholder/thin templates merely to populate the library.
SYSTEM_TEMPLATES: tuple[SystemTemplate, ...] = ()


def published_templates() -> tuple[SystemTemplate, ...]:
    return tuple(item for item in SYSTEM_TEMPLATES if item.status == "published")


def get_system_template(slug: str, *, include_drafts: bool = False) -> SystemTemplate | None:
    for item in SYSTEM_TEMPLATES:
        if item.slug == slug and (include_drafts or item.status == "published"):
            return item
    return None


def template_library_enabled() -> bool:
    return bool(published_templates())
