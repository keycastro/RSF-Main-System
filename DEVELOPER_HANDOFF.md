# Developer Handoff

This repository is the single source-code project for the Key Castro public website and private online owner inbox.

Read in order:

1. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md` *(local/private roadmap on the owner's working copy)*
2. `docs/FUTURE_TEMPLATE_LIBRARY_ROADMAP.md` *(local/private roadmap on the owner's working copy)*
3. `NEXT_DEVELOPER_READ_THIS_FIRST.md`
4. `docs/INTEGRATED_PAGE_INTRO_FLOW_3_5_3.md`
5. `docs/SITE_WIDE_PAGE_TOP_REFINEMENT_3_5_2.md`
6. `docs/WEBSITE_SIMPLIFICATION_3_5.md`
7. `docs/UX_ORGANIZATION_AND_VISUAL_REFINEMENT_3_4.md`
8. `docs/UX_INFORMATION_ARCHITECTURE.md`
9. `docs/VISUAL_PRESENTATION_3_0.md`
10. `docs/SYSTEM_SEARCH_AND_ACCESS_MODEL_3_1.md`
11. `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md`
12. `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`
13. `docs/TEMPLATE_LIBRARY_FOUNDATION.md`
14. `PROJECT_STATE.json`
15. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`
16. `SECURITY_AND_SHARING_NOTES.md`

Do not split the owner inbox back into a separate project folder. Do not expose owner-only routes or secrets in public UI, GitHub, logs, screenshots, or documentation.

## Public IA contract from 2.9.0

Primary navigation is **Home · Systems · Services · About · Contact**.

`Systems` is the one public browse destination for the two published independent systems. `/projects` is a permanent legacy redirect to `/system-templates`; do not recreate a second competing systems catalog without a new, distinct information need.

The old `/skills` and `/experience` URLs now permanently redirect to `/about`. They are not separate visitor destinations or sitemap entries.

The two published systems remain separate applications and must stay separate in claims, screenshots, workflow, and metadata. Do not publish placeholder/thin systems. Read `docs/PUBLISHED_SYSTEM_TEMPLATES.md` before changing their public positioning.



## Integrated page-intro contract from 3.5.3

Inner public pages must not render the title as a visually detached banner. Systems, Services, About, and Contact use the same paper surface as the content below, no hero divider, and the title container aligns with the main content container. The first useful section follows immediately with controlled spacing. System detail pages keep title + preview together but use the same continuous-surface principle. Home retains its stronger orientation hero. See `docs/INTEGRATED_PAGE_INTRO_FLOW_3_5_3.md`.

## Page-top proportion contract from 3.5.2

Public page introductions are deliberately compact. `page-hero-simple` should read as a short introduction, not a large banner, and the first useful section should follow without a large blank gap. Home keeps a stronger opening but avoids wasted vertical travel. System-detail title/preview areas and the 404 page use the same proportion rule. Preserve readable spacing; compact does not mean cramped. See `docs/SITE_WIDE_PAGE_TOP_REFINEMENT_3_5_2.md`.

## System-card separation contract from 3.5.1

Home and Systems use subtle per-system visual identities so the two published systems read as separate choices. Property Operations uses a restrained warm tint; Property Inventory uses a restrained cool tint. Separation also relies on border, spacing, typography, focus, and card structure — never color alone. Preserve dark readable copy, existing navy buttons, search, pricing placement, routes, and system independence. See `docs/SYSTEM_CARD_VISUAL_SEPARATION_3_5_1.md`.

## Simplification contract from 3.5.0

Keep public content short, simple, and easy to understand. Home should orient, Systems should help visitors choose, each system detail page should explain and price that one system, Services should show only the two ways to work with Key Castro, About should stay brief, and Contact should be direct. Do not re-add repeated pricing to Home or the Systems catalog. `/skills` and `/experience` redirect to `/about`. See `docs/WEBSITE_SIMPLIFICATION_3_5.md`.

## Organization and hierarchy contract from 3.4.0

Keep the existing Home · Systems · Services · About · Contact mental model, but preserve the 3.4.0 reduction in duplicated CTAs and card mass. System catalog cards have one dominant action. System detail pages centralize monthly/yearly subscription decisions in the subscription section; customization remains available without competing equally at every stage. Supporting credibility pages use compact structured rows. See `docs/UX_ORGANIZATION_AND_VISUAL_REFINEMENT_3_4.md`.

## Presentation contract from 3.0.0

Keep the premium KEY CASTRO identity, but do not return to screenshot-led pages with natural-ratio images consuming most of the viewport. Catalog and homepage previews must remain controlled and compact; system detail screenshots remain expandable through the lightbox. Preserve readable type and obvious actions while keeping vertical travel intentional. See `docs/VISUAL_PRESENTATION_3_0.md`.


## Search and access contract from 3.1.0

Systems search is a compact progressive enhancement over the server-rendered catalog. Search terms come from reusable system metadata, not JavaScript slug branches. Preserve keyboard use, visible focus, result status, clear/reset behavior, and the helpful no-match path to `Contact Me`.

The previous free-access model is retired. The current model is **Managed System Subscription + Paid Customization**. Public managed-subscription pricing is **$49/month or $490/year per system**, with $98/year savings on the yearly option. Pricing comes from one trusted source in `app/system_templates.py`. Business-specific development is scoped and priced separately, and the normal subscription continues while the managed system remains in use. See `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md` and `docs/MANAGED_SUBSCRIPTION_PRICING_3_3.md`.
