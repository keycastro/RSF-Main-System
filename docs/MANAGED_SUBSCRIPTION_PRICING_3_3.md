> **HISTORICAL NOTE (3.6.0):** Commercial wording in this document reflects an older release and is superseded by `docs/BUSINESS_MODEL_AND_MANAGED_MAINTENANCE_3_6.md`. Do not restore the old subscription-access model.

# KEY CASTRO — Managed Subscription Pricing Contract (3.3.0)

## Approved public pricing

Every currently published ready-made system uses the same managed subscription pricing:

- **Monthly:** $49/month per system
- **Yearly:** $490/year per system
- 12 monthly payments total $588
- **Yearly savings:** $98/year

There is no third tier, per-seat tier, setup fee, lifetime plan, ownership price, or source-code price in the public offer.

## Single source of truth

Pricing lives in `app/system_templates.py` as `MANAGED_SUBSCRIPTION_PRICING`.

Templates, Contact plan selection, annual-savings display, and trusted inquiry attribution render from that source. Do not hardcode competing price values in templates or JavaScript.

## Contact and inquiry plan handling

Subscription CTAs may pass only the plan key `monthly` or `yearly`. The server resolves that key against `MANAGED_SUBSCRIPTION_PRICING`.

Browser-submitted price text is never trusted or stored as authoritative pricing. Invalid plan keys do not create an official plan selection.

No database migration is required. For plan-specific subscription inquiries, the existing `source_action` field stores a trusted server-generated historical label such as:

`System Subscription — Monthly · $49/month`

The private owner Inbox separates that stored value into:

- Request: System Subscription
- Plan: Monthly · $49/month

Historical inquiries and old generic `System Subscription` rows remain valid.

## Paid Customization remains separate

Paid Customization has no public fixed price. Requirements, scope, and development price are discussed separately.

The customization fee pays for requested development work. The normal monthly or yearly managed subscription continues while the client keeps using the managed system.

## Service boundary

Subscription means managed access. It does not transfer source-code ownership, permanent ownership, or lifetime access.

Do not promise unlimited users, storage, bandwidth, integrations, support, or lifetime hosting. Standard hosting, database operation, standard updates, ordinary maintenance, and basic support are included within the agreed managed-service scope.

## Presentation rule

Pricing must stay compact and secondary to the system's business purpose:

- compact inline pricing on Systems cards
- clear monthly/yearly choice on system detail pages
- concise price mention on Home and Services
- no giant SaaS pricing tables
- no extra tiers or marketplace styling

The 3.0 compact presentation and 3.1 metadata-driven Systems search remain intact.
