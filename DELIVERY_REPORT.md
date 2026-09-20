# DELIVERY REPORT — KEY CASTRO 3.8.15

## Scope

Home-page lower CTA simplification only. The former three-step **How it works.** summary is removed; the final **See Services & Pricing →** link remains and still points to `/services`.

## Public change

- Removed the old Home heading, supporting sentence, steps 1–3, numbering, and all step descriptions.
- Retained exactly one final CTA: **See Services & Pricing →**.
- Centered and slightly enlarged the CTA with minimal Home-scoped CSS and balanced desktop/mobile spacing so the area feels intentionally designed before the footer.

## Preserved

- All other Home content.
- Primary navigation and `/services` route.
- Services & Pricing page content.
- Current pricing: $160 existing system, $79 minor upgrade, $149 major upgrade, Price by Agreement for New System / Large Expansion, and $39/month or $390/year maintenance.
- Three published systems.
- Footer content.
- Contact flow, owner Inbox, database, authentication, CSRF, and inquiry storage.
- Existing GitHub/Render one-command deployment workflow.

## Release rule

Production is not considered 3.8.15 until the one-run deployer passes the complete test suite and verifies the live version, simplified Home CTA, removal of the old Home three-step block, approved pricing/content boundaries, footer, and exactly three published systems.
