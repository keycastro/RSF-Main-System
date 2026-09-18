# DELIVERY REPORT — KEY CASTRO 3.2.0

## Scope

Commercial-model migration only. The compact 3.0 presentation, 3.1 metadata-driven Systems search, Flask architecture, PostgreSQL inquiry flow, private owner Inbox, SEO, sitemap, robots, GitHub/Render setup, and desktop launchers are preserved.

## Public model after 3.2.0

- **Managed System Subscription** — ongoing managed access to an existing KEY CASTRO system. Monthly/yearly terms and pricing are discussed before activation.
- **Paid Customization** — separately scoped and priced development work when a subscriber needs business-specific changes. The normal subscription continues while the managed system remains in use.
- Visitors needing something completely different can still discuss a custom system.

## Migration

- Removed current public free-standard/free-template/free-access messaging.
- New contact intent: `subscribe` -> `System Subscription`.
- Customization intent: `customize` -> `Paid Customization`.
- Legacy `free-access` URLs/forms normalize to the new subscription intent; no database schema migration is required.
- Existing historical inquiry rows are not rewritten.

## Safety

No public price, source-code ownership, permanent ownership, unlimited hosting/storage/users/support, or lifetime-hosting promise is introduced.
