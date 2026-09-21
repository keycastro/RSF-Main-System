# REALTY SYSTEMS FOUNDRY — DEVELOPER HANDOFF

## v3.9.8 collection-handling recovery

The current migration blocker was Windows PowerShell 5.1 empty-collection parameter binding after production settings had already been resolved. The v3.9.8 updater normalizes optional collections internally and avoids the failing intermediate sanitizer call. Preserve this behavior.

**Release:** 3.9.8

## v3.9.8 Render hostname migration

Use the one-run updater. It obtains a Render API key only for the migration, reads the original service's direct environment variables and secret files in memory, validates production requirements, clones the service, copies production configuration before the authoritative deploy, verifies the public site and private RSF Inbox, then records the new active service ID. Never commit or persist the API key or secret values.

---

# REALTY SYSTEMS FOUNDRY WEBSITE — DEVELOPER HANDOFF

**Historical previous release:** 3.9.3
**Current live URL:** https://realtysystemsfoundry.onrender.com
**Preferred domain:** https://realtysystemsfoundry.com
**Founder:** Key Castro
**Framework:** Flask

## Current direction

Version 3.9.3 keeps the approved public rebrand and local workspace identity and migrates to a newly cloned Render service named `realtysystemsfoundry` so the official Render URL can be `https://realtysystemsfoundry.onrender.com`. The replacement service has a new service ID. GitHub repository names, database connection, design, systems, and pricing remain unchanged, while the original service is retained as a rollback service.

Version 3.9.0 rebrands the public website as **Realty Systems Foundry**, a real-estate technology systems company. The Home headline is **“We Build Custom Systems for Real Estate Businesses.”** Key Castro is presented as **Founder, Realty Systems Foundry**. Existing-system pricing remains **$199 one-time**; self-management remains **$0/month management fee**; optional company-managed care remains **$39/month or $390/year**. The current visual identity, cards, typography, routes, pages, footer style, systems, backend, and private functionality are preserved.

Primary navigation: **Home · Systems · Services & Pricing · About · Contact**. The underlying `/services` URL remains unchanged.

## Architecture and private boundary

Keep the current single Flask codebase. The public website/contact flow and private owner Inbox stay in the same project. The owner Inbox remains protected, unlisted, noindexed, and authenticated.

## Published systems

1. Property Operations Command Center
2. Property Inventory Hub
3. Student Housing Matching and Placement System

Never merge their codebases, screenshots, or claims. Student Housing remains independent portfolio work and must not be described as commissioned, adopted, endorsed, or AI-powered.

## Business rules

Purchase: every published existing system is **$199 one-time**. The purchase does not include customization or maintenance.

Changes: **Minor System Upgrade — $79**, **Major System Upgrade — $149**, **New System / Large Expansion — Price by Agreement**.

New custom system from scratch: **Price by Agreement**.

After the system is ready there are exactly two management options:

- Full Handover — “We build it. You manage it.” — **$0/month management fee**; client handles the technical side.
- Managed by Realty Systems Foundry — “We build it. We manage it.” — optional **$39/month or $390/year**; Realty Systems Foundry handles the technical side.

Maintenance keeps the current system running; it does not include new features, workflow changes, new modules, integrations, or other improvements. Public customer-facing pricing uses USD only.

The customer-facing page uses **You Manage It** / **We Manage It** so the visitor does not need to learn internal terminology.

## UX rule

A non-technical 50–70 year old business owner should understand the basic offer after one reading. Keep the complete management model on Services & Pricing; system pages should explain the system itself. Use concrete actions such as “Your team signs in” and “Search for the property you need.”

## Release workflow

Use the existing one-run updater/deployer. Success requires tests, approved Git staging, both Git pushes, successful Render deploy, and live health/Home featured-CTA/content/profile-portrait/rebrand verification for version 3.9.8. Never commit private/runtime files.


### v3.9.0 direct change
Public rebrand to **Realty Systems Foundry**. Main headline: **We Build Custom Systems for Real Estate Businesses.** Key Castro is shown as founder. Company-first `we/our` language replaces personal service language where appropriate. Current design and approved pricing remain unchanged. Internal `KEY_CASTRO`/`keycastro` infrastructure identifiers remain for deployment compatibility.

### v3.8.18 direct change
Home hero secondary CTA label: **Create a New System** (destination remains `/contact`). No other public content or behavior is changed by this release.



### v3.8.20 direct change
Existing ready-built system price: **$199 one-time**. This release changes price only. Self-managed technical care remains **$0/month management fee**; optional KEY CASTRO managed care remains **$39/month / $390/year**. No redesign.

### v3.8.19 direct change
Existing ready-built system price: **$290 one-time**. Services & Pricing now clearly states that technical management is optional: **$0/month management fee** if the client manages it, or the unchanged **$39/month / $390/year** if KEY CASTRO manages it. No overall redesign.

## v3.9.3 local workspace identity
The active local project path is `C:\Users\Admin\Documents\REALTY_SYSTEMS_FOUNDRY`. The desktop shortcuts are `REALTY SYSTEMS FOUNDRY` and `RSF INBOX`. The installer migrates the previous `KEY_CASTRO_WEBSITE` folder in place when safe so `.git`, `.env`, `.owner_inbox.json`, `.venv`, and other local state are preserved. GitHub repository names remain unchanged. The v3.9.3 migration creates a replacement Render service and records its new service ID in `PROJECT_STATE.json`; the original service ID is retained there as the legacy rollback source.


## v3.9.3 Render hostname migration correction

Production testing proved that changing the original Render service name did not reassign its existing `onrender.com` hostname. The approved target remains `https://realtysystemsfoundry.onrender.com`. v3.9.3 therefore creates a new Render service by cloning the original service configuration with Render CLI `services create --from`, verifies the new public host and the private RSF Inbox/database continuity, then records the replacement service ID for future deployments. The original service is retained as `realtysystemsfoundry-legacy` for rollback and is not deleted automatically. Public design, systems, and pricing are unchanged.


## v3.9.8 Render env-var key validation

The updater validates and sanitizes environment-variable keys before any Render API write. Malformed legacy keys are skipped without printing secret values. Critical production variables remain mandatory, and the original service remains the rollback until the exact new hostname and private inbox/database continuity are verified.
