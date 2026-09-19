# NEXT DEVELOPER — READ THIS FIRST

**Release version:** 3.8.0
**Official site:** https://keycastro.onrender.com
**Framework:** Flask

## Read first

1. `docs/HUMAN_CLARITY_AND_OLDER_USER_UX_3_8.md`
2. `docs/BUSINESS_MODEL_AND_MANAGED_MAINTENANCE_3_6.md`
3. `PROJECT_STATE.json`
4. `README.md`
5. `SECURITY_AND_SHARING_NOTES.md`
6. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`
7. `docs/DEPLOYMENT_HISTORY.md`

Historical subscription-access documents are superseded. Do not restore the old subscription/free-access model.

## Public information architecture

Primary navigation:

```text
Home
Systems
How It Works
About
Contact
```

The canonical route remains `/services`; only the public label is **How It Works**. Keep `/system-templates` as the canonical systems route.

## Visitor language rule

Write for a first-time non-technical older business owner. Public copy should use concrete everyday actions before technical/business terminology. A visitor should quickly understand:

- Key Castro builds simple systems for real estate businesses.
- They can choose an existing system or ask for a new one.
- After the build, they can manage it or Key Castro can manage it.
- They contact Key Castro to start.

Do not restore abstract homepage process words such as **Choose / Adapt / Deliver**. Do not force visitors to understand **Full Handover**, **managed maintenance**, **workflow**, **roles**, **deployment**, or similar terms to understand the basic offer.

## Published systems

- Property Operations Command Center
- Property Inventory Hub
- Student Housing Matching and Placement System

Keep all three separate. Student Housing is an independent portfolio project, not a commissioned/adopted/endorsed client product. Do not claim AI matching.

## Commercial model — AUTHORITATIVE

### Creation

1. Customize an existing KEY CASTRO system.
2. Build a new custom system.

Build/customization pricing is quoted separately.

### After build — EXACTLY TWO OPTIONS

1. **Full Handover** — “I build it. You manage it.”
2. **Managed by KEY CASTRO** — “I build it. I manage it.” — **$49/month or $490/year**.

Public beginner-facing labels are **You Manage It** and **I Manage It**. Keep the formal terms internal/secondary where necessary. Do not add a third option.

## Page responsibility

- Home explains what KEY CASTRO does.
- Systems shows the systems already built.
- System detail explains one system.
- How It Works explains the business process and management options.
- About explains Key Castro simply.
- Contact collects the inquiry.

Do not repeat the full management model on every system page.

## Design rule

Preserve the existing ivory/navy/sage brand and 3.7 compact composition. Version 3.8.0 adds larger everyday text, fewer micro-labels, fewer competing CTAs, and simpler language. Compact must never mean tiny text.

## Security

Never expose `.env`, owner tokens, database credentials, GitHub/Render secrets, private access codes, SMTP passwords, secret keys, private Inbox routes, or real client data.

## Release rule

Use `APPLY_UPDATE_AND_DEPLOY_LIVE.bat`. It must update locally, preserve `.env`, run tests, stage approved files only, commit, push both repositories, deploy Render, and verify production. Do not claim a release is live until the terminal prints:

`LIVE DEPLOYMENT VERIFIED SUCCESSFULLY`
