# KEY CASTRO WEBSITE

Professional portfolio for **KEY CASTRO — Custom Real Estate Systems Developer**.

Official website: https://keycastro.onrender.com

## One project folder

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

This single codebase contains:

- Public portfolio and systems website
- Completed-system detail pages
- Contact form
- Inquiry database integration
- Private online owner inbox

## Desktop shortcuts

- **KEY CASTRO** — opens the public live website.
- **KEY CASTRO INBOX** — securely opens the private online owner inbox.

The inbox is not linked or advertised anywhere on the public website. It does not run a localhost server.

## Production

Flask + Gunicorn on the existing Render service. Render auto-deploy is off; use the documented explicit push + deploy workflow.

## Visual design system

Version 2.6.0 delivers the high-end commercial visual system:

- warm neutral backgrounds
- deep blue primary accents
- muted green supporting accents
- architectural section layering with ivory, soft white, navy, sage, and restrained bronze
- stronger typography, spacing, hierarchy, screenshot framing, buttons, forms, and case-study structure
- intentionally readable metadata and supporting text instead of ultra-small low-contrast labels
- a premium business-tool treatment for the private owner inbox

The core visual identity, inbox privacy, and deployment architecture remain unchanged.

## Public information architecture

Version 2.9.0 simplifies the public journey to **Home · Systems · Services · About · Contact**. The previous Projects index duplicated the same published systems, so `/projects` now permanently redirects to the single Systems library at `/system-templates`. Skills and Experience remain public/indexable secondary pages reached through About/footer. See `docs/UX_INFORMATION_ARCHITECTURE.md`.

## Future system-template foundation

Version 2.7.0 prepared the reusable template foundation. Version 2.8.0 activates that architecture with two real systems: **Property Operations Command Center** and **Property Inventory Hub**. Each remains an independent completed system and free standard template by request; business-specific customization is paid development. See `docs/TEMPLATE_LIBRARY_FOUNDATION.md` and `docs/PUBLISHED_SYSTEM_TEMPLATES.md`.
