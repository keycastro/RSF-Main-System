# KEY CASTRO — Business Model + Managed Maintenance (3.6.0)

**Status: CURRENT / AUTHORITATIVE**

Version 3.6.0 replaces the old subscription-access commercial model.

## How a client gets a system

A client can either:

1. **Customize an existing KEY CASTRO system** — start from a working system and adapt the workflow, fields, roles, permissions, branding, terminology, reports, or business rules.
2. **Build a custom system** — create a system around the client's own workflow when the existing systems are not a suitable starting point.

Development/customization is quoted separately based on requirements. The managed-maintenance price is not the build price.

## After the system is ready — only two options

### Option 1 — Full Handover

**I build it. You manage it.**

After the agreed build and payment terms are complete, the system is handed over according to the agreement. The client becomes responsible for ongoing hosting, domain, backups, maintenance, updates, infrastructure/provider accounts, and future technical management. The client may manage it internally or hire another developer later.

### Option 2 — Managed by KEY CASTRO

**I build it. I manage it.**

KEY CASTRO continues handling the agreed technical management. Managed maintenance may include hosting/deployment management, backups, maintenance, bug fixes, agreed updates, monitoring, and technical support.

Current public managed-maintenance pricing:

- **$49/month per system**
- **$490/year per system**
- yearly savings versus 12 monthly payments: **$98/year**

Pricing is sourced from `MANAGED_MAINTENANCE_PRICING` in `app/system_templates.py`. Major new features and custom development remain separately quoted.

## Legacy compatibility

Old external `subscribe` and `free-access` inquiry links are accepted only for backward compatibility and normalize to **Managed by KEY CASTRO**. Historical `System Subscription` and `Paid Customization` inquiry records remain readable in the private Inbox but display using current terminology where possible.

Do not restore the old rule that the software is only subscription access or that ownership can never be handed over.
