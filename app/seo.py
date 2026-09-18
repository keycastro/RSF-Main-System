from __future__ import annotations

from typing import Iterable


def absolute_url(base_url: str, path: str) -> str:
    if path.startswith(("https://", "http://")):
        return path
    base = (base_url or "").rstrip("/")
    if not base:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def core_structured_data(base_url: str, socials: dict[str, str]) -> list[dict]:
    """Truthful site/person entities shared by public pages."""
    if not base_url:
        return []

    same_as = [url for url in socials.values() if url]
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": f"{base_url}#key-castro",
        "name": "Key Castro",
        "url": base_url,
        "jobTitle": "Custom Real Estate Systems Developer",
        "knowsAbout": [
            "Custom real estate software",
            "Property operations systems",
            "Rental property workflows",
            "Property maintenance workflows",
            "Real estate listing systems",
        ],
    }
    if same_as:
        person["sameAs"] = same_as

    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{base_url}#website",
        "url": base_url,
        "name": "Key Castro",
        "description": "Custom real estate systems and web applications for property, listing, rental, maintenance, and team workflows.",
        "creator": {"@id": f"{base_url}#key-castro"},
    }
    return [person, website]


def breadcrumb_structured_data(base_url: str, items: Iterable[tuple[str, str]]) -> dict | None:
    if not base_url:
        return None
    elements = []
    for position, (name, path) in enumerate(items, start=1):
        elements.append(
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": absolute_url(base_url, path),
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def software_template_structured_data(base_url: str, template) -> list[dict]:
    """Schema emitted only for a real published template page."""
    if not base_url or template.status != "published":
        return []

    page_url = absolute_url(base_url, f"/system-templates/{template.slug}")
    software = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": template.name,
        "description": template.meta_description,
        "url": page_url,
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web browser",
        "creator": {"@id": f"{base_url}#key-castro"},
    }
    data = [software]

    video = template.video
    if all((video.name, video.description, video.thumbnail, video.upload_date)) and (
        video.url or video.embed_url
    ):
        video_schema = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": video.name,
            "description": video.description,
            "thumbnailUrl": absolute_url(base_url, video.thumbnail),
            "uploadDate": video.upload_date,
        }
        if video.url:
            video_schema["contentUrl"] = video.url
        if video.embed_url:
            video_schema["embedUrl"] = video.embed_url
        data.append(video_schema)
    return data
