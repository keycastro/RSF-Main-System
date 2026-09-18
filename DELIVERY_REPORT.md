# KEY CASTRO WEBSITE — INFORMATION ARCHITECTURE CLEANUP 2.9.0

Version 2.9.0 reorganizes the existing production website without rebuilding or changing its Flask/PostgreSQL/Render architecture.

## Main UX changes

- Replaced the competing `Projects` + `System Templates` top-level choices with one public destination: **Systems**.
- Added explicit **Home** navigation for first-time/non-technical visitors.
- `/projects` now permanently redirects to `/system-templates`; the duplicate Projects index template is removed.
- Simplified the homepage to identity → systems → free-vs-custom rule → final contact CTA.
- Simplified system cards to purpose, audience, free-standard status, and obvious actions.
- Standardized system detail pages and removed the immediate duplicate access/customization block.
- Moved technical build information into progressive disclosure so business information remains dominant.
- Reframed Services around paid work rather than repeating system categories.
- Simplified About and moved Skills/Experience to secondary navigation through About/footer.
- Simplified Contact while preserving trusted template/request context through PostgreSQL into the private inbox.
- Increased navigation/action readability and simplified small-screen presentation.

## Preserved

- Both independent published systems and their stable URLs.
- Free standard access vs paid customization behavior.
- Contact → PostgreSQL → private KEY CASTRO INBOX.
- Owner authentication and private/public separation.
- SEO metadata, canonical URLs, structured data, robots, and sitemap behavior.
- Flask server-rendered architecture, GitHub repositories, Render service, and desktop launchers.
- Nexus remains removed from current public presentation.

See `docs/UX_INFORMATION_ARCHITECTURE.md` for the ongoing information-architecture contract.
