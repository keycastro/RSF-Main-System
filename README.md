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

The visual system began with the premium 2.6.0 direction. Version 3.4.0 keeps that identity while refining organization, hierarchy, and presentation density:

- warm neutral backgrounds
- deep blue primary accents
- muted green supporting accents
- architectural section layering with ivory, soft white, navy, sage, and restrained bronze
- stronger typography, spacing, hierarchy, screenshot framing, buttons, forms, and case-study structure
- intentionally readable metadata and supporting text instead of ultra-small low-contrast labels
- a premium business-tool treatment for the private owner inbox
- controlled screenshot previews instead of giant screenshot-led cards
- shorter header, hero, page-hero, section, CTA, and footer proportions
- compact system-detail galleries with full-size lightbox inspection
- fewer repeated CTA sections and clearer action hierarchy
- editorial row/list patterns on supporting pages instead of unnecessary large cards
- centralized subscription decisions on system detail pages

The core visual identity, inbox privacy, and deployment architecture remain unchanged. See `docs/VISUAL_PRESENTATION_3_0.md` and `docs/UX_ORGANIZATION_AND_VISUAL_REFINEMENT_3_4.md`.

## Public information architecture

Version 2.9.0 simplified the public journey to **Home · Systems · Services · About · Contact**. Version 3.4.0 preserves that architecture while making page purpose, action hierarchy, and content density clearer. The previous Projects index duplicated the same published systems, so `/projects` now permanently redirects to the single Systems library at `/system-templates`. Skills and Experience remain public/indexable secondary pages reached through About/footer. See `docs/UX_INFORMATION_ARCHITECTURE.md`.

## Future system-template foundation

Version 2.7.0 prepared the reusable system-template foundation and 2.8.0 published the first two real systems. Version 3.2.0 established the **Managed System Subscription + Paid Customization** model. Version 3.3.0 adds the approved public subscription pricing: **$49/month or $490/year per system**, with $98/year savings on the yearly option, while keeping Paid Customization separately quoted. See `docs/TEMPLATE_LIBRARY_FOUNDATION.md`, `docs/PUBLISHED_SYSTEM_TEMPLATES.md`, `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md`, and `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`.


## Systems search and access model

Version 3.1.0 adds an accessible, metadata-driven, real-time filter to the server-rendered Systems page. The search is intentionally lightweight: JavaScript filters the normal HTML system cards without changing routes, SEO content, or the Flask architecture. Empty search results lead naturally to the existing custom-system Contact path.

The commercial boundary is explicit: subscription pays for ongoing managed access at the approved public price; customization pays separately for requested development work, and the subscription continues while the managed system remains in use. Pricing is centralized in `app/system_templates.py`. See `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md` and `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`.
