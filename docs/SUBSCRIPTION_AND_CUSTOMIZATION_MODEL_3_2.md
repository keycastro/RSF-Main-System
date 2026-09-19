# KEY CASTRO — Managed Subscription + Paid Customization Contract (3.2.0 foundation; pricing updated by 3.3.0)

## Current commercial model

KEY CASTRO has two primary commercial offers:

1. **Managed System Subscription** — ongoing managed access to an existing ready-made system. From 3.3.0, the approved public price is **$49/month or $490/year per system**, with $98/year savings on yearly billing. Pricing comes from the trusted source in `app/system_templates.py`. The site still does not invent user/storage quotas or unlimited-resource promises. Subscription access does not transfer ownership of the core software.
2. **Paid Customization** — separate development work when a subscribed system needs business-specific changes. Requirements and development price are agreed separately. The customization fee pays for development work; the normal subscription continues while the client keeps using the managed system.

If no ready-made system fits, a visitor can still discuss a completely custom system through Contact.

## Public wording rules

Retired public wording: FREE STANDARD SYSTEM, Free Template Access, Request Free Access, free standard version, no software cost, or language implying free hosted access.

Preferred wording:
- MANAGED SYSTEM SUBSCRIPTION
- View Subscription / Get monthly access / Get yearly access
- System Subscription
- PAID CUSTOMIZATION
- Request Paid Customization
- Discuss a Custom System

Do not say rent, buy the software, own the source code, permanent ownership, lifetime license, unlimited hosting/storage/users/support, or lifetime hosting unless the owner explicitly changes the model later.

## Inquiry attribution

New template-origin actions use:
- `subscribe` -> `System Subscription` or a trusted plan-specific label such as `System Subscription — Monthly · $49/month`
- `customize` -> `Paid Customization`

The retired `free-access` intent is accepted only for backward compatibility with old external links/forms and is normalized to `subscribe` / `System Subscription`. System identity is still resolved from trusted server-side registry metadata.

No database schema migration is required: the existing `source_action` text field stores the new labels. Historical rows are left unchanged as historical records.

## Security and architecture

This change does not alter Flask, PostgreSQL, owner authentication, private Inbox, sitemap architecture, canonical system URLs, real-time Systems search, GitHub repositories, Render deployment, or desktop launchers.
