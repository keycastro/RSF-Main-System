# KEY CASTRO WEBSITE — COMPACT PREMIUM PRESENTATION REDESIGN 3.0.0

Version 3.0.0 significantly rebalances the existing production website presentation without rebuilding or changing its Flask/PostgreSQL/Render architecture.

## Why this release exists

The 2.9.0 information architecture is correct, but the live layout still inherited oversized screenshot and spacing rules from older portfolio designs. System previews were visually dominant, pages traveled too far vertically, the sticky header/hero/page heroes were taller than necessary, and supporting cards/CTAs retained more mass than the simplified content required.

## Main presentation changes

- Reduced sticky-header height while keeping navigation readable and obvious.
- Replaced the near-full-viewport homepage hero with a shorter editorial hero and compact business-system brief.
- Reduced default section/page-hero/CTA/footer vertical mass.
- Rebuilt homepage system cards as balanced text + compact preview compositions.
- Rebuilt the Systems catalog cards so information and action are primary and the screenshot is supporting evidence.
- Reworked system detail heroes around a compact preview with existing click-to-expand lightbox access.
- Reworked additional system screenshots into a controlled-height gallery.
- Tightened workflow, feature, scope, Services, About, Contact, and footer spacing without shrinking essential text.
- Added explicit mobile ordering and image-height controls so system pages do not become giant screenshot stacks.

## Preserved

- 2.9.0 information architecture: Home · Systems · Services · About · Contact.
- Property Operations Command Center and Property Inventory Hub as two separate systems.
- Free standard system access and paid customization behavior.
- Contact → PostgreSQL → private KEY CASTRO INBOX attribution.
- Owner authentication/private routes.
- SEO, canonical URLs, structured data, sitemap, robots, stable system URLs.
- Flask server-rendered architecture, GitHub repositories, exact-commit Render deployment, and desktop launchers.

See `docs/VISUAL_PRESENTATION_3_0.md` for the presentation contract and non-regression rules.
