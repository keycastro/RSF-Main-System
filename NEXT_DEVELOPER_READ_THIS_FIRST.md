# NEXT DEVELOPER — READ THIS FIRST

**Current version:** 3.7.0
**Official site:** https://keycastro.onrender.com
**Positioning:** KEY CASTRO — Custom Real Estate Systems Developer

## Read first

1. `docs/MASTER_UX_REFINEMENT_3_7.md`
2. `docs/BUSINESS_MODEL_AND_MANAGED_MAINTENANCE_3_6.md`
3. `PROJECT_STATE.json`
4. `README.md`
5. `SECURITY_AND_SHARING_NOTES.md`
6. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`
7. `docs/DEPLOYMENT_HISTORY.md`
8. `docs/PUBLISHED_SYSTEM_TEMPLATES.md`
9. `docs/UX_INFORMATION_ARCHITECTURE.md`
10. 3.5.x visual-refinement documents for the preserved design rules

Historical 3.2/3.3 subscription documents are retained for history only and are **superseded** by the current 3.6 business model and 3.7 UX state. Do not restore the old subscription-access model.

## Architecture

Keep one Flask codebase in `C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE`. It contains the public website/contact flow and the private owner Inbox. Do not split or rewrite the architecture without a real technical reason.

## Public information architecture

Primary navigation stays:

```text
Home
Systems
Services
About
Contact
```

Use **Systems** as the public mental model. Canonical system routes remain under `/system-templates`. Preserve existing redirects, SEO, sitemap behavior, Contact security, owner Inbox security, and deployment architecture.

## Published systems

- Property Operations Command Center
- Property Inventory Hub
- Student Housing Matching and Placement System

`app/system_templates.py` is the source-controlled registry. These systems are separate applications. Never mix screenshots, features, workflows, databases, or product names.

The Student Housing system is an independent portfolio project. Do not claim that the original market poster hired, paid, approved, adopted, or endorsed it.

## Current commercial model — AUTHORITATIVE

### System creation

- **Customize an existing system**
- **Build a custom system**

Development/customization is quoted separately based on requirements.

### After the system is ready — ONLY TWO OPTIONS

1. **Full Handover** — “I build it. You manage it.” Client handles ongoing hosting, domain, backups, maintenance, updates, and future technical management after handover.
2. **Managed by KEY CASTRO** — “I build it. I manage it.” KEY CASTRO handles the agreed managed service for **$49/month or $490/year per system**.

The monthly/yearly price is for **managed maintenance**, not software access and not the custom-build price. Pricing comes from `MANAGED_MAINTENANCE_PRICING` in `app/system_templates.py`.

Legacy `subscribe` / `free-access` URLs may normalize to the current managed-service inquiry for compatibility. Do not expose the old wording publicly.

## Visitor flow

```text
Home → Systems → System → Customize / Build → Full Handover OR Managed by KEY CASTRO → Contact
```

## Design rule

Version 3.7.0 is the current visual baseline. Preserve its premium ivory/navy/sage identity, compact header and page rhythm, balanced three-system grid, controlled screenshots, simple English, and responsive behavior. Do not restore the older oversized or 2+1 card composition.

## Security

Never expose `.env`, owner tokens, database credentials, Render/GitHub secrets, private access codes, SMTP passwords, secret keys, private Inbox routes, or real private client data.


## Default release rule — automatic live deployment

Whenever a KEY CASTRO website release package changes the site, include and use the one-run `APPLY_UPDATE_AND_DEPLOY_LIVE.bat` workflow. A successful update must not stop after local installation: it runs tests, pushes the approved release to both Git remotes, triggers the existing Render service, and verifies the live site before reporting success. Render provider-level auto-deploy remains off; the controlled release script performs the deployment.
