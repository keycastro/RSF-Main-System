# KEY CASTRO WEBSITE — DEVELOPER HANDOFF

**Release:** 3.8.12
**Live URL:** https://keycastro.onrender.com
**Framework:** Flask

## Current direction

Version 3.8.12 is a **targeted existing-system pricing clarity update**. Every published existing system is **$160 one-time**. That price is for the existing system as shown; requested changes are separate upgrades. Maintenance and new custom builds remain separate. No unrelated redesign or backend rewrite is part of this release.

Primary navigation: **Home · Systems · How It Works · About · Contact**. The underlying `/services` URL remains unchanged.

## Architecture and private boundary

Keep the current single Flask codebase. The public website/contact flow and private owner Inbox stay in the same project. The owner Inbox remains protected, unlisted, noindexed, and authenticated.

## Published systems

1. Property Operations Command Center
2. Property Inventory Hub
3. Student Housing Matching and Placement System

Never merge their codebases, screenshots, or claims. Student Housing remains independent portfolio work and must not be described as commissioned, adopted, endorsed, or AI-powered.

## Business rules

Purchase: every published existing system is **$160 one-time**. The purchase does not include customization or maintenance.

Changes: **Minor System Upgrade — $79**, **Major System Upgrade — $149**, **New System / Large Expansion — Custom Quote**.

New custom system from scratch: **Custom Quote**.

After the system is ready there are exactly two management options:

- Full Handover — “I build it. You manage it.”
- Managed by KEY CASTRO — “I build it. I manage it.” — **$39/month or $390/year**.

Maintenance keeps the current system running; it does not include new features, workflow changes, new modules, integrations, or other improvements. Public customer-facing pricing uses USD only.

The customer-facing page uses **You Manage It** / **I Manage It** so the visitor does not need to learn internal terminology.

## UX rule

A non-technical 50–70 year old business owner should understand the basic offer after one reading. Keep the complete management model on How It Works; system pages should explain the system itself. Use concrete actions such as “Your team signs in” and “Search for the property you need.”

## Release workflow

Use the existing one-run updater/deployer. Success requires tests, approved Git staging, both Git pushes, successful Render deploy, and live health/content/profile-portrait verification for version 3.8.12. Never commit private/runtime files.
