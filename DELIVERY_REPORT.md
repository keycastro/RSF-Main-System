# DELIVERY REPORT — KEY CASTRO 3.6.0

## Scope

Business-model and portfolio update inside the existing Flask website. The established design, navigation, private Inbox, deployment architecture, and public/private security boundary are preserved.

## Public changes

- Existing systems are clearly available for customization.
- Visitors may also request a completely custom system.
- After a system is ready, only two choices are presented: **Full Handover** or **Managed by KEY CASTRO**.
- $49/month and $490/year now clearly mean **managed maintenance**, not software access and not custom development.
- Added the **Student Housing Matching and Placement System** as a third independent portfolio system using synthetic sample screenshots and truthful independent-project wording.
- Contact/inquiry intents now support customization, custom build, full handover, managed service, monthly maintenance, and yearly maintenance while preserving legacy-link compatibility.

## Preserved

- premium ivory/navy/sage design
- Home · Systems · Services · About · Contact navigation
- Flask architecture
- canonical system routes and redirects
- metadata-driven Systems search
- Contact → inquiry database → private Inbox flow
- CSRF and trusted server-side source/price context
- SEO, sitemap, structured data, Open Graph/Twitter metadata
- manual Render deployment architecture

## Safety

Distributable releases must exclude `.env`, `.owner_inbox.json`, logs, caches, private inquiry data, database dumps, access codes, tokens, and Python bytecode. Student Housing website screenshots use a fresh synthetic demo database.
