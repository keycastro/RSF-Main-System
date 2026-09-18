# NEXT DEVELOPER — READ THIS FIRST

**Current version:** 3.0.0
**Official site:** https://keycastro.onrender.com
**Positioning:** KEY CASTRO — Custom Real Estate Systems Developer

## Read first

Before changing the website, read:

1. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md` (local/private roadmap)
2. `docs/FUTURE_TEMPLATE_LIBRARY_ROADMAP.md` (local/private roadmap)
3. `docs/UX_INFORMATION_ARCHITECTURE.md`
4. `docs/TEMPLATE_LIBRARY_FOUNDATION.md`
5. `PROJECT_STATE.json`
6. `SECURITY_AND_SHARING_NOTES.md`
7. `docs/DEPLOYMENT_HISTORY.md`
8. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`

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

Both are completed systems built by Key Castro and offered as free standard systems **by request**. Business-specific customization is paid development. They are separate applications: never mix their screenshots, features, workflows, databases, or product names.

`app/system_templates.py` remains the source-controlled registry. Contact attribution includes `source_type`, `source_slug`, `source_title`, and `source_action`, allowing the private Inbox to distinguish free-template access from customization requests.

Nexus Properties remains removed from current public presentation.

## UX rule

Before adding any visible page, card, CTA, or section, ask whether it creates a genuinely new decision or information need. Do not duplicate information already explained more clearly elsewhere. Preserve the visitor flow:

```text
Home → Systems → System → Free Access or Customization → Contact
```

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
