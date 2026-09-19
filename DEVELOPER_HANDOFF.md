# KEY CASTRO WEBSITE — DEVELOPER HANDOFF

**Release:** 3.8.0
**Live URL:** https://keycastro.onrender.com
**Framework:** Flask

## Current direction

Version 3.8.0 preserves the established website and its 3.7 visual refinement but makes the public experience deliberately beginner-friendly and older-user-friendly. Public pages use everyday English, larger readable text, fewer competing actions, and one primary purpose per page.

Primary navigation: **Home · Systems · How It Works · About · Contact**. The underlying `/services` URL remains unchanged.

## Architecture and private boundary

Keep the current single Flask codebase. The public website/contact flow and private owner Inbox stay in the same project. The owner Inbox remains protected, unlisted, noindexed, and authenticated.

## Published systems

1. Property Operations Command Center
2. Property Inventory Hub
3. Student Housing Matching and Placement System

Never merge their codebases, screenshots, or claims. Student Housing remains independent portfolio work and must not be described as commissioned, adopted, endorsed, or AI-powered.

## Business rules

Creation: customize an existing system OR build a new system.

After build there are exactly two options:

- Full Handover — “I build it. You manage it.”
- Managed by KEY CASTRO — “I build it. I manage it.” — $49/month or $490/year.

The customer-facing page uses **You Manage It** / **I Manage It** so the visitor does not need to learn internal terminology.

## UX rule

A non-technical 50–70 year old business owner should understand the basic offer after one reading. Keep the complete management model on How It Works; system pages should explain the system itself. Use concrete actions such as “Your team signs in” and “Search for the property you need.”

## Release workflow

Use the existing one-run updater/deployer. Success requires tests, approved Git staging, both Git pushes, successful Render deploy, and live health/content verification for version 3.8.0. Never commit private/runtime files.
