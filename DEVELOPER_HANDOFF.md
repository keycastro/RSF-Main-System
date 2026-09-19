# KEY CASTRO WEBSITE — DEVELOPER HANDOFF

**Version:** 3.7.0

## Product state

KEY CASTRO is an existing Flask portfolio/business website. Version 3.7.0 keeps the established architecture, business model, security boundaries, and brand while applying the master site-wide UX simplification and visual refinement.

## Current public navigation

Home · Systems · Services · About · Contact

Canonical system routes remain `/system-templates` and `/system-templates/<slug>`.

## Published systems

1. Property Operations Command Center
2. Property Inventory Hub
3. Student Housing Matching and Placement System

All are independent systems. Existing systems may be customized for a client's business. The Student Housing system is independent portfolio proof based on market research; no client relationship or endorsement is claimed.

## Commercial model

A client starts by either customizing an existing system or requesting a custom build. Development/customization is quoted separately.

After the system is ready, there are only two options:

- **Full Handover** — KEY CASTRO builds/customizes it; client takes responsibility for ongoing hosting, domain, backups, maintenance, updates, and technical management after handover.
- **Managed by KEY CASTRO** — KEY CASTRO continues the agreed technical management for $49/month or $490/year per system.

The current price values are managed-maintenance prices, not software-access prices and not development prices. Source of truth: `MANAGED_MAINTENANCE_PRICING` in `app/system_templates.py`.

Legacy inquiry strings and URLs are normalized for backward compatibility. Historical records remain readable in the private Inbox.

## Contact / inquiry trust boundary

Never trust browser-submitted price text or system titles. The server resolves published system metadata, request type, and official monthly/yearly plan pricing before writing inquiry context. Generic Contact submissions still work.

## Private owner Inbox

Keep it private, absent from public navigation/sitemap, and protected by the existing authenticated launcher/session flow. Do not expose bearer tokens or environment secrets.

## Design / UX

Preserve the 3.7.0 ivory/navy/sage visual baseline, balanced three-column system presentation, compact information density, controlled screenshot previews, accessible focus states, five-item navigation, and simple English. Do not restore the older oversized layouts or centered odd third card.

## Deployment

Render remains the official host with manual deployment. Follow `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`. Do not claim production deployment until the pushed commit and Render deployment are verified.

## Historical docs

Documents named around `SUBSCRIPTION`, 3.2.0, or 3.3.0 describe older commercial states. They are historical only. Current authority is `docs/BUSINESS_MODEL_AND_MANAGED_MAINTENANCE_3_6.md`.


## Default release rule — automatic live deployment

Whenever a KEY CASTRO website release package changes the site, include and use the one-run `APPLY_UPDATE_AND_DEPLOY_LIVE.bat` workflow. A successful update must not stop after local installation: it runs tests, pushes the approved release to both Git remotes, triggers the existing Render service, and verifies the live site before reporting success. Render provider-level auto-deploy remains off; the controlled release script performs the deployment.
