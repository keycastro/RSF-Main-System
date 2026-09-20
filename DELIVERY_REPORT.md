# DELIVERY REPORT — KEY CASTRO 3.8.12

## Scope

Focused existing-system pricing clarity update. No unrelated redesign or backend rewrite.

## Approved business model

- **Existing published system — $160 one-time.**
- The $160 price is for the existing system as shown; changes are separate paid upgrades.
- **Minor System Upgrade — $79.**
- **Major System Upgrade — $149.**
- **New System / Large Expansion — Custom Quote.**
- Optional maintenance remains **$39/month or $390/year**.
- A completely new custom system remains **Custom Quote**.
- Public pricing uses USD only.

## Public changes

- Home cards show the $160 one-time price.
- Systems cards show the $160 one-time price and the page explains that changes are separate.
- System detail pages show the $160 one-time price and use **Get This System** for the purchase inquiry path.
- How It Works Step 1 now separates **$160 existing system** from **Custom Quote new system** while Step 2 maintenance and later upgrades remain separate.

## Preserved

- Three published systems.
- Current How It Works Step 2 management/maintenance organization.
- About page, navigation, footer, screenshots, owner Inbox, database, authentication, CSRF, and inquiry storage.
- Existing Render/GitHub one-command deployment workflow.

## Release rule

Production is not considered 3.8.12 until the one-run deployer verifies the live version, $160 existing-system pricing, USD-only public pricing, purchase/upgrade/maintenance separation, approved upgrade and maintenance prices, preserved About content, footer, and exactly three published systems.
