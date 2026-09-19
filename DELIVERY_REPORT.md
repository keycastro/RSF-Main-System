# DELIVERY REPORT — KEY CASTRO 3.3.0

## Scope

Pricing release only. The existing 3.2 Managed System Subscription + Paid Customization model remains intact. The compact 3.0 presentation, 3.1 metadata-driven Systems search, Flask architecture, PostgreSQL inquiry flow, private owner Inbox, SEO, sitemap, robots, GitHub/Render setup, and desktop launchers are preserved.

## Approved pricing

- **$49/month per system**
- **$490/year per system**
- 12 monthly payments = $588
- yearly savings = **$98/year**

Pricing is defined once in `app/system_templates.py` and rendered from that trusted metadata.

## Contact / Inbox plan handling

- Monthly and yearly subscription CTAs use trusted plan keys.
- The server resolves the official price; browser-submitted price text is ignored.
- No database schema migration is required.
- Existing `source_action` stores the trusted plan-specific subscription label when a plan is selected.
- Private Inbox presentation separates Request and Plan for readability.
- Existing generic and historical inquiry rows remain backward compatible.

## Paid Customization

Customization remains separately quoted development work. It does not replace the managed subscription. The regular subscription continues while the client uses the managed system.

## Safety

No new ownership/source-code promise, lifetime plan, setup fee, per-seat tier, unlimited-resource promise, fake checkout, or additional commercial package is introduced.
