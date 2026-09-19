# KEY CASTRO WEBSITE

Professional portfolio for **KEY CASTRO — Custom Real Estate Systems Developer**.

Official website: https://keycastro.onrender.com

## One project folder

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

This single codebase contains:

- Public portfolio and systems website
- Completed-system detail pages
- Contact form
- Inquiry database integration
- Private online owner inbox

## Desktop shortcuts

- **KEY CASTRO** — opens the public live website.
- **KEY CASTRO INBOX** — securely opens the private online owner inbox.

The inbox is not linked or advertised anywhere on the public website. It does not run a localhost server.

## Production

Flask + Gunicorn on the existing Render service. Render auto-deploy is off; use the documented explicit push + deploy workflow.

## Public design and content rule

Version 3.5.0 keeps the existing premium visual identity but makes the public website much simpler:

- short headings and paragraphs
- basic, easy-to-understand English
- fewer repeated explanations
- fewer buttons and choices
- pricing shown on system detail pages instead of repeated across Home and Systems
- simpler Services, About, Contact, and footer content
- compact screenshots that support the page instead of dominating it
- one clear purpose per page

The public rule is: **Short. Simple. Clear. No unnecessary repetition.**

See `docs/WEBSITE_SIMPLIFICATION_3_5.md`.

## Public information architecture

Primary navigation remains **Home · Systems · Services · About · Contact**. `/projects` permanently redirects to `/system-templates`. `/skills` and `/experience` now permanently redirect to `/about` so the normal visitor journey has fewer pages and fewer duplicate explanations.

## Future system-template foundation

Version 2.7.0 prepared the reusable system-template foundation and 2.8.0 published the first two real systems. Version 3.2.0 established the **Managed System Subscription + Paid Customization** model. Version 3.3.0 adds the approved public subscription pricing: **$49/month or $490/year per system**, with $98/year savings on the yearly option, while keeping Paid Customization separately quoted. See `docs/TEMPLATE_LIBRARY_FOUNDATION.md`, `docs/PUBLISHED_SYSTEM_TEMPLATES.md`, `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md`, and `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`.


## Systems search and access model

Version 3.1.0 adds an accessible, metadata-driven, real-time filter to the server-rendered Systems page. The search is intentionally lightweight: JavaScript filters the normal HTML system cards without changing routes, SEO content, or the Flask architecture. Empty search results lead naturally to the existing custom-system Contact path.

The commercial boundary is explicit: subscription pays for ongoing managed access at the approved public price; customization pays separately for requested development work, and the subscription continues while the managed system remains in use. Pricing is centralized in `app/system_templates.py`. See `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md` and `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`.
