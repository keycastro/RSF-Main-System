# KEY CASTRO WEBSITE — DEVELOPER HANDOFF

**Release:** 3.8.20
**Live URL:** https://keycastro.onrender.com
**Framework:** Flask

## Current direction

Version 3.8.20 changes only the existing ready-built system price to **$199 one-time**. The Services & Pricing management model remains exactly as approved: self-management has **$0/month management fee**, while optional KEY CASTRO management remains **$39/month or $390/year**. The current visual identity, cards, typography, routes, pages, footer, systems, backend, and private functionality are preserved.

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

- Full Handover — “I build it. You manage it.” — **$0/month management fee**; client handles the technical side.
- Managed by KEY CASTRO — “I build it. I manage it.” — optional **$39/month or $390/year**; KEY CASTRO handles the technical side.

Maintenance keeps the current system running; it does not include new features, workflow changes, new modules, integrations, or other improvements. Public customer-facing pricing uses USD only.

The customer-facing page uses **You Manage It** / **I Manage It** so the visitor does not need to learn internal terminology.

## UX rule

A non-technical 50–70 year old business owner should understand the basic offer after one reading. Keep the complete management model on Services & Pricing; system pages should explain the system itself. Use concrete actions such as “Your team signs in” and “Search for the property you need.”

## Release workflow

Use the existing one-run updater/deployer. Success requires tests, approved Git staging, both Git pushes, successful Render deploy, and live health/Home featured-CTA/content/profile-portrait verification for version 3.8.20. Never commit private/runtime files.


### v3.8.18 direct change
Home hero secondary CTA label: **Create a New System** (destination remains `/contact`). No other public content or behavior is changed by this release.



### v3.8.20 direct change
Existing ready-built system price: **$199 one-time**. This release changes price only. Self-managed technical care remains **$0/month management fee**; optional KEY CASTRO managed care remains **$39/month / $390/year**. No redesign.

### v3.8.19 direct change
Existing ready-built system price: **$290 one-time**. Services & Pricing now clearly states that technical management is optional: **$0/month management fee** if the client manages it, or the unchanged **$39/month / $390/year** if KEY CASTRO manages it. No overall redesign.
