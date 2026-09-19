# KEY CASTRO WEBSITE

Professional portfolio and client-acquisition website for **KEY CASTRO — Custom Real Estate Systems Developer**.

Official website: https://keycastro.onrender.com

**Current release version: 3.8.7**

## One project folder

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

This single Flask codebase contains the public website, published system pages, Contact workflow, inquiry database integration, and the private online owner Inbox.

## Public design rule

Preserve the premium ivory/navy/sage identity, typography, compact spacing, responsive behavior, and five-item navigation. Version 3.8.7 preserves the approved v3.8.6 site and implements only the approved About top profile design: portrait/name/title on the left and ABOUT / What I do. / exact service summary / compact value row on the right; styling remains scoped to the About page.

Public rule: **Short. Simple. Clear. No unnecessary repetition.**

Primary navigation remains **Home · Systems · How It Works · About · Contact**. Stable system routes remain under `/system-templates`.

## Current business model

A client can:

- **Customize an existing system**, or
- **Request a custom system**.

After the agreed system is ready, there are only two management choices:

1. **Full Handover — I build it. You manage it.** The client handles ongoing hosting, domain, backups, maintenance, updates, and future technical management after handover.
2. **Managed by KEY CASTRO — I build it. I manage it.** KEY CASTRO continues the agreed hosting/deployment, backups, maintenance, fixes, updates, monitoring, and technical support for **$49/month or $490/year per system**.

Build/customization pricing is separate and quoted based on requirements. Monthly/yearly pricing is for managed maintenance, not the cost of a custom build.

See `docs/BUSINESS_MODEL_AND_MANAGED_MAINTENANCE_3_6.md`.

## Published systems

- Property Operations Command Center
- Property Inventory Hub
- Student Housing Matching and Placement System

All three are independent systems. Never mix their screenshots, workflows, databases, or product claims. Existing systems can be customized for a client's business.

The Student Housing Matching and Placement System is an **independent portfolio project** built after studying a real publicly visible student-housing operations problem. It must not be presented as commissioned by, affiliated with, or endorsed by the original poster.

## Systems architecture

Published systems are registered in `app/system_templates.py` and rendered through:

- `/system-templates`
- `/system-templates/<slug>`

Systems search remains a metadata-driven client-side enhancement, but it is intentionally hidden while the catalog has six or fewer systems. With the current three-system catalog, visitors see the choices directly without an unnecessary search control.

## Private owner Inbox

The private owner Inbox remains part of this Flask codebase but is not linked, advertised, or indexed publicly. It uses the existing protected online authentication flow and inquiry database.

## Production

Flask + Gunicorn on the existing Render service. Render provider-level auto-deploy remains off, but KEY CASTRO release packages now use the controlled one-run `APPLY_UPDATE_AND_DEPLOY_LIVE.bat` workflow: local update → tests → approved Git commit/push → Render deploy → live verification. See `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`.

## Security

Never include `.env`, `.owner_inbox.json`, logs, private inquiry data, database dumps, access codes, tokens, or other secrets in a distributable release.
