# NEXT DEVELOPER — READ THIS FIRST

**Release version:** 3.9.8

## Critical v3.9.8 Render migration rule

Do not rely on `render services create --from` alone for this production service. The clone flow currently omits direct service environment variables. The approved updater copies the source service environment variables and secret files with the official Render API in memory before the replacement service's verified deploy. Keep the original service as rollback until the new hostname and private inbox are confirmed.

---

# NEXT DEVELOPER — READ THIS FIRST

**Historical previous release:** 3.9.3
**Current live site:** https://realtysystemsfoundry.onrender.com
**Preferred custom domain:** https://realtysystemsfoundry.com
**Founder:** Key Castro
**Framework:** Flask

## Read first

1. `README.md`
2. `PROJECT_STATE.json`
3. `DEVELOPER_HANDOFF.md`
4. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md`
5. `docs/CONTENT_AND_SCOPE.md`
6. `docs/HUMAN_CLARITY_AND_OLDER_USER_UX_3_8.md`
7. `SECURITY_AND_SHARING_NOTES.md`
8. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`
9. `docs/DEPLOYMENT_HISTORY.md`

Older versioned pricing/business-model documents are historical. Current 3.9.8 pricing and service rules in the files above supersede older prices. Do not restore the old subscription/free-access model or the old $49/$490 maintenance price.

## Current release change

Version 3.9.3 migrates the public Render hostname by cloning the original service configuration into a newly created service named `realtysystemsfoundry`. The replacement service gets a new service ID; the original service is retained as `realtysystemsfoundry-legacy` for rollback. GitHub repositories, local workspace identity, public design, content, systems, database connection, and pricing are preserved.

Version 3.9.0 rebrands the public website as **Realty Systems Foundry**. The Home headline is **“We Build Custom Systems for Real Estate Businesses.”** Key Castro is shown as **Founder, Realty Systems Foundry**. Existing ready-built systems remain **$199 one-time**. The Services & Pricing management choice remains unchanged: self-managed technical care is **$0/month management fee**; optional Realty Systems Foundry managed care remains **$39/month or $390/year**.

## Public information architecture

Primary navigation:

```text
Home
Systems
Services & Pricing
About
Contact
```

The canonical route remains `/services`; only the public label is **Services & Pricing**. Keep `/system-templates` as the canonical systems route.

## Visitor language rule

Write for a first-time non-technical older business owner. Public copy should use concrete everyday actions before technical/business terminology. A visitor should quickly understand:

- Realty Systems Foundry builds custom software systems and automation for real estate businesses.
- They can buy a published existing system for **$199 one-time**, or ask for a completely new system at **Price by Agreement**.
- Changes to an existing system are separate upgrades; after the system is ready, they can manage it or Realty Systems Foundry can manage it.
- They contact Realty Systems Foundry to start.

Do not restore abstract homepage process words such as **Choose / Adapt / Deliver**. Do not force visitors to understand **Full Handover**, **managed maintenance**, **workflow**, **roles**, **deployment**, or similar terms to understand the basic offer.

## Published systems

- Property Operations Command Center
- Property Inventory Hub
- Student Housing Matching and Placement System

Keep all three separate. Student Housing is an independent portfolio project, not a commissioned/adopted/endorsed client product. Do not claim AI matching.

## Commercial model — AUTHORITATIVE

### Purchase / creation

1. Buy a published existing Realty Systems Foundry system — **$199 one-time**.
2. Build a completely new custom system — **Price by Agreement**.

The $199 existing-system price is for the system as shown. Requested changes are separate upgrades.

### After build — EXACTLY TWO OPTIONS

1. **Full Handover** — “We build it. You manage it.” — **$0/month management fee**; the client handles the technical side.
2. **Managed by Realty Systems Foundry** — “We build it. We manage it.” — optional **$39/month or $390/year**; Realty Systems Foundry handles the technical side.

Public beginner-facing labels are **You Manage It** and **We Manage It**. Keep the formal terms internal/secondary where necessary. Do not add a third management option.

Current price rules: existing published system = **$199 one-time**; Minor System Upgrade = **$79**; Major System Upgrade = **$149**; New System / Large Expansion = **Price by Agreement**; maintenance = **$39/month or $390/year**; completely new custom system = **Price by Agreement**. Purchase, upgrades, maintenance, and new custom builds are separate. Public pricing uses USD only.

## Page responsibility

- Home explains what Realty Systems Foundry does.
- Systems shows the systems already built.
- System detail explains one system.
- Services & Pricing explains the business process, pricing, and management options.
- About explains Realty Systems Foundry first, then Key Castro as founder, plus the problems the company solves, automation value, and the potential to reduce dependence on too many separate paid tools.
- Contact collects the inquiry.

Do not repeat the full management model on every system page.

## Design rule

Preserve the existing ivory/navy/sage brand and Human Clarity composition. Preserve the approved Home transition after the three featured system cards. The approved CTA band uses **Explore All Systems →** to `/system-templates` as the primary action and **See Services & Pricing →** to `/services` as the secondary action, with restrained decorative microcopy and responsive CTA-only styling. Keep the three cards, hero, navigation, footer content, all other pages, pricing, and private functionality unchanged. Compact must never mean tiny text.

## Security

Never expose `.env`, owner tokens, database credentials, GitHub/Render secrets, private access codes, SMTP passwords, secret keys, private Inbox routes, or real client data.

## Release rule

Use `APPLY_UPDATE_AND_DEPLOY_LIVE.bat`. It must update locally, preserve `.env`, run tests, stage approved files only, commit, push both repositories, deploy Render, and verify production. Do not claim a release is live until the terminal prints:

`LIVE DEPLOYMENT VERIFIED SUCCESSFULLY`


### v3.9.0 direct change
Public rebrand to **Realty Systems Foundry**. Main headline: **We Build Custom Systems for Real Estate Businesses.** Key Castro is shown as founder. Use company-first `we/our` language. Preserve the current design, three-system catalog, and all approved pricing. Internal `KEY_CASTRO`/`keycastro` folder/repository/Render identifiers remain until a separate infrastructure migration is approved.

### v3.8.18 direct change
Home hero secondary CTA label: **Create a New System** (destination remains `/contact`). No other public content or behavior is changed by this release.



### v3.8.20 direct change
Existing ready-built system price is **$199 one-time**. Management pricing is unchanged: **You Manage It = $0/month management fee**; **I Manage It = $39/month or $390/year**. Preserve the current design and the two-option model.

### v3.8.19 direct change
Existing ready-built system price is **$290 one-time**. On Services & Pricing, make it unmistakable that management is optional: **You Manage It = $0/month management fee**; **I Manage It = $39/month or $390/year**, unchanged. Preserve the current design and keep the two-option model.

## v3.9.3 local workspace identity
The active local project path is `C:\Users\Admin\Documents\REALTY_SYSTEMS_FOUNDRY`. The desktop shortcuts are `REALTY SYSTEMS FOUNDRY` and `RSF INBOX`. The installer migrates the previous `KEY_CASTRO_WEBSITE` folder in place when safe so `.git`, `.env`, `.owner_inbox.json`, `.venv`, and other local state are preserved. GitHub repository names remain unchanged. The active Render service is the new cloned `realtysystemsfoundry` service, and its service ID is recorded into `PROJECT_STATE.json` by the migration workflow. The original service ID remains recorded as the legacy rollback service.


## v3.9.3 Render hostname migration correction

Production testing proved that changing the original Render service name did not reassign its existing `onrender.com` hostname. The approved target remains `https://realtysystemsfoundry.onrender.com`. v3.9.3 therefore creates a new Render service by cloning the original service configuration with Render CLI `services create --from`, verifies the new public host and the private RSF Inbox/database continuity, then records the replacement service ID for future deployments. The original service is retained as `realtysystemsfoundry-legacy` for rollback and is not deleted automatically. Public design, systems, and pricing are unchanged.


## v3.9.8 Render env-var key validation

The updater validates and sanitizes environment-variable keys before any Render API write. Malformed legacy keys are skipped without printing secret values. Critical production variables remain mandatory, and the original service remains the rollback until the exact new hostname and private inbox/database continuity are verified.
