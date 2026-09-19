# NEXT DEVELOPER — READ THIS FIRST

**Current version:** 3.4.0
**Official site:** https://keycastro.onrender.com
**Positioning:** KEY CASTRO — Custom Real Estate Systems Developer

## Read first

Before changing the website, read:

1. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md` (local/private roadmap)
2. `docs/FUTURE_TEMPLATE_LIBRARY_ROADMAP.md` (local/private roadmap)
3. `docs/UX_ORGANIZATION_AND_VISUAL_REFINEMENT_3_4.md`
4. `docs/UX_INFORMATION_ARCHITECTURE.md`
5. `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md`
6. `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`
7. `docs/TEMPLATE_LIBRARY_FOUNDATION.md`
8. `PROJECT_STATE.json`
9. `SECURITY_AND_SHARING_NOTES.md`
10. `docs/DEPLOYMENT_HISTORY.md`
11. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`

## Current architecture

This is one Flask codebase in:

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

It contains the public website/contact flow and the private owner inbox. Do not split them into separate active projects.

## 2.9.0 public information architecture

Primary public navigation is deliberately limited to:

```text
Home
Systems
Services
About
Contact
```

Use **Systems** as the visible public mental model for completed systems. The stable technical/SEO route remains `/system-templates`.

`/projects` is a permanent legacy redirect to `/system-templates`. Do not rebuild a duplicate Projects index. `/projects/<published-system-slug>` remains a compatibility redirect to the canonical system detail page.

`/skills` and `/experience` remain public/indexable but secondary; they are reached from About/footer rather than primary navigation.

## Published systems

- `Property Operations Command Center` → `/system-templates/property-operations-command-center`
- `Property Inventory Hub` → `/system-templates/property-inventory-hub`

Both are completed systems built by Key Castro and offered through **Managed System Subscription** access. Business-specific changes are **Paid Customization** scoped and priced separately. The normal subscription continues while the managed system remains in use. They are separate applications: never mix their screenshots, features, workflows, databases, or product names.

`app/system_templates.py` remains the source-controlled registry. Contact attribution includes `source_type`, `source_slug`, `source_title`, and `source_action`, allowing the private Inbox to distinguish managed subscription requests, plan-specific subscription context, and customization requests.

Nexus Properties remains removed from current public presentation.

## UX rule

Before adding any visible page, card, CTA, or section, ask whether it creates a genuinely new decision or information need. Do not duplicate information already explained more clearly elsewhere. Preserve the visitor flow:

```text
Home → Systems → System → System Subscription or Paid Customization → Contact
```


## 3.4.0 organization + hierarchy rule

Version 3.4.0 keeps the established public IA but removes repeated decisions and unnecessary visual mass. Home now has one orientation flow; Systems cards have one dominant action; Services/About/Skills/Experience use lighter editorial structures; System detail pages centralize subscription decisions instead of repeating them in multiple CTA panels. Preserve the compact screenshots, metadata-driven search, trusted pricing, SEO routes, and public/private security boundary. See `docs/UX_ORGANIZATION_AND_VISUAL_REFINEMENT_3_4.md`.

## 3.0.0 presentation rule

The 2.9.0 information architecture remains authoritative. Version 3.0.0 changes **presentation density**, not the public mental model.

- Screenshots support the system explanation; they must not dominate a viewport.
- Systems cards use controlled/cropped previews and concise information.
- System detail hero screenshots are compact previews with full-size lightbox access.
- Additional screenshots stay in a controlled gallery.
- Keep header, hero, sections, CTAs, cards, footer, and mobile spacing intentionally compact.
- Preserve readable text and obvious buttons; compact does not mean tiny.
- Do not revert to giant 16:10 screenshots at full card width or full-viewport hero height.

See `docs/VISUAL_PRESENTATION_3_0.md`.

## 3.1.0 system search + 3.2.0 commercial rule

The Systems page includes a lightweight client-side search. It is progressive enhancement: published systems are rendered in normal server HTML and JavaScript only filters existing cards. Search indexing remains metadata-driven through `SystemTemplate.search_text` / `search_terms`; do not add slug-specific JavaScript.

Current commercial rule from 3.2.0, with approved pricing added in 3.3.0:

- **Managed System Subscription** = ongoing managed access to an existing published system at **$49/month or $490/year per system**. The yearly option saves $98 compared with 12 monthly payments.
- **Paid Customization** = separately scoped and priced development work when a subscribed system needs business-specific changes. The normal subscription continues while the managed system remains in use.
- Pricing is rendered from `MANAGED_SUBSCRIPTION_PRICING` in `app/system_templates.py`; do not hardcode competing prices in templates or JavaScript.

Do not imply source-code ownership, lifetime access, unlimited infrastructure, or unlimited support.

See `docs/SYSTEM_SEARCH_AND_ACCESS_MODEL_3_1.md`, `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md`, and `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`.
