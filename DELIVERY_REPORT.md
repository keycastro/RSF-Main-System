# DELIVERY REPORT — KEY CASTRO 3.8.1

## Scope

Strict minor change to **How It Works** only, plus direct test/release/deployment dependencies. No redesign, route change, business-model change, or unrelated content change.

## Approved changes

- Existing-system card sentence: **“I can adapt one of my existing systems to fit your business.”**
- Removed redundant Step 2: **“I build the system.”** and its two supporting lines.
- Renumbered **“Choose who manages it.”** from Step 3 to Step 2.
- Preserved the final **Want to get started?** CTA exactly.
- Preserved **You Manage It**, **I Manage It**, **$49/month**, and **$490/year**.

## Preserved

- v3.8.0 Human Clarity visual design, ivory/navy/sage identity, typography, spacing, header, footer, and navigation
- `/services` route
- Home, Systems, About, Contact, and all three system-detail pages
- Flask architecture, contact/database flow, private owner Inbox, CSRF/authentication, SEO, sitemap, robots, redirects
- three published systems and two-option business model

## Release rule

Production is not considered 3.8.1 until the one-run deployer verifies the live health version, exact How It Works change, final CTA, pricing, and all three published systems.
