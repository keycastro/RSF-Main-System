# NEXT DEVELOPER — READ THIS FIRST

**Release version:** 3.8.15
**Official site:** https://keycastro.onrender.com
**Framework:** Flask

## Read first

1. `README.md`
2. `PROJECT_STATE.json`
3. `DEVELOPER_HANDOFF.md`
4. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md`
5. `docs/CONTENT_AND_SCOPE.md`
6. `docs/HUMAN_CLARITY_AND_OLDER_USER_UX_3_8.md`
7. `SECURITY_AND_SHARING_NOTES.md`
8. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`
9. `docs/DEPLOYMENT_HISTORY.md`

Older versioned pricing/business-model documents are historical. Current 3.8.15 pricing and service rules in the files above supersede older prices. Do not restore the old subscription/free-access model or the old $49/$490 maintenance price.

## Public information architecture

Primary navigation:

```text
Home
Systems
Services & Pricing
About
Contact
```

The canonical route remains `/services`; only the public label is **Services & Pricing**. Keep `/system-templates` as the canonical systems route.

## Visitor language rule

Write for a first-time non-technical older business owner. Public copy should use concrete everyday actions before technical/business terminology. A visitor should quickly understand:

- Key Castro builds custom business systems and automation for real estate, property, and housing businesses.
- They can buy a published existing system for **$160 one-time**, or ask for a completely new system at **Price by Agreement**.
- Changes to an existing system are separate upgrades; after the system is ready, they can manage it or Key Castro can manage it.
- They contact Key Castro to start.

Do not restore abstract homepage process words such as **Choose / Adapt / Deliver**. Do not force visitors to understand **Full Handover**, **managed maintenance**, **workflow**, **roles**, **deployment**, or similar terms to understand the basic offer.

## Published systems

- Property Operations Command Center
- Property Inventory Hub
- Student Housing Matching and Placement System

Keep all three separate. Student Housing is an independent portfolio project, not a commissioned/adopted/endorsed client product. Do not claim AI matching.

## Commercial model — AUTHORITATIVE

### Purchase / creation

1. Buy a published existing KEY CASTRO system — **$160 one-time**.
2. Build a completely new custom system — **Price by Agreement**.

The $160 existing-system price is for the system as shown. Requested changes are separate upgrades.

### After build — EXACTLY TWO OPTIONS

1. **Full Handover** — “I build it. You manage it.”
2. **Managed by KEY CASTRO** — “I build it. I manage it.” — **$39/month or $390/year**.

Public beginner-facing labels are **You Manage It** and **I Manage It**. Keep the formal terms internal/secondary where necessary. Do not add a third management option.

Current price rules: existing published system = **$160 one-time**; Minor System Upgrade = **$79**; Major System Upgrade = **$149**; New System / Large Expansion = **Price by Agreement**; maintenance = **$39/month or $390/year**; completely new custom system = **Price by Agreement**. Purchase, upgrades, maintenance, and new custom builds are separate. Public pricing uses USD only.

## Page responsibility

- Home explains what KEY CASTRO does.
- Systems shows the systems already built.
- System detail explains one system.
- Services & Pricing explains the business process, pricing, and management options.
- About explains Key Castro, the problems the service solves, automation value, and the potential to reduce dependence on too many separate paid tools.
- Contact collects the inquiry.

Do not repeat the full management model on every system page.

## Design rule

Preserve the existing ivory/navy/sage brand and Human Clarity composition. Version 3.8.15 changes only the final lower Home area: the old three-step process summary is removed and only the polished **See Services & Pricing →** CTA remains. Keep navigation, all other Home sections, the Services & Pricing page, pricing, systems, footer content, About, Contact, and private functionality unchanged. Compact must never mean tiny text.

## Security

Never expose `.env`, owner tokens, database credentials, GitHub/Render secrets, private access codes, SMTP passwords, secret keys, private Inbox routes, or real client data.

## Release rule

Use `APPLY_UPDATE_AND_DEPLOY_LIVE.bat`. It must update locally, preserve `.env`, run tests, stage approved files only, commit, push both repositories, deploy Render, and verify production. Do not claim a release is live until the terminal prints:

`LIVE DEPLOYMENT VERIFIED SUCCESSFULLY`
