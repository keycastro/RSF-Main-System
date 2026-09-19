# KEY CASTRO — UX Organization & Visual Refinement 3.4.0

## Purpose

Version 3.4.0 is a presentation and information-architecture refinement inside the existing Flask project. It does **not** replace the framework, routes, database, owner authentication, pricing source, contact attribution, search architecture, deployment workflow, or public/private boundary.

The goal is to make the existing website feel clearer, calmer, more deliberate, and faster to scan while preserving the established KEY CASTRO identity and commercial model.

## Master audit

### A. What was confusing

- The homepage introduced the same subscription/customization distinction more than once and ended with another similar CTA.
- System detail pages presented subscription/customization choices in the hero, again in the pricing section, and again in a final CTA panel.
- Services used large equal-weight cards even though there are only two primary commercial paths.
- Skills and Experience used large card grids for supporting credibility content, making secondary pages visually heavier than their role justified.

### B. What was redundant

- Repeated commercial explanations across Home, Services, System details, and final CTA panels.
- Multiple equal or near-equal CTAs on system detail pages.
- Repeated “view systems” CTA panels at the bottom of secondary credibility pages.
- Large card treatments used for content that could be communicated more clearly as structured rows.

### C. What was merged

- Homepage “two services” explanation and final custom-system CTA were consolidated into one clear “How to work with Key Castro” decision section.
- System-detail subscription access information is now concentrated in one subscription decision area.
- About’s approach content is presented as one editorial section with a structured process list instead of three visually independent cards.

### D. What remains separate

- Property Operations Command Center and Property Inventory Hub remain completely separate systems.
- Managed System Subscription and Paid Customization remain distinct commercial concepts.
- Skills and Experience remain separate secondary public/indexable pages.
- Public website and private owner Inbox remain separated by the existing security model.

### E–G. Primary navigation and final navigation architecture

Primary navigation remains:

`Home · Systems · Services · About · Contact`

No new primary destination was added. Skills and Experience remain secondary destinations through About/footer. `/projects` remains the permanent legacy redirect to `/system-templates`.

### H. Homepage hierarchy

1. Clear identity and business promise.
2. Two simple visitor paths: use an existing system or discuss custom work.
3. Completed systems with one dominant action per system.
4. One concise section explaining the two commercial paths.

The previous extra closing CTA section was removed because it repeated the same decision.

### I. Page-type hierarchies

**Systems catalog:** page purpose → search → system cards → no-match custom-development path.

**System detail:** identity → controlled preview → business problem/audience → workflow/features → additional screenshots → subscription decision → customization disclosure → technical details.

**Services:** page purpose → two editorial service paths → payment/access distinction.

**About:** identity → build approach → specialization → secondary credibility links.

**Skills/Experience:** identity → compact structured list → contextual navigation.

**Contact:** request context → next-step explanation → focused form.

### J. Ideal visitor journey

`Home → Systems → System Detail → Monthly/Yearly Access → Contact`

Alternative path:

`Home/Services/System Detail → Customization or Custom System → Contact`

### K. Redundancy map

- Full subscription explanation lives primarily on System detail and Services.
- Systems catalog shows only compact pricing and one action.
- Homepage gives a short orientation, not a full policy explanation.
- Contact reflects the selected system/intent/plan without re-teaching the whole commercial model.

### L–P. Oversized visuals, vertical space, media, layout, and card overuse

- Homepage and catalog screenshots remain compact evidence rather than dominant content.
- Detail hero screenshot height is reduced again and retains full-size lightbox access.
- Additional gallery previews are shorter.
- Global section spacing is reduced without shrinking readable text.
- Services, About process, Skills, and Experience move away from large card grids toward editorial rows and bordered lists.

### Q–T. Typography, width, spacing, and density

- Heading scale is reduced slightly and normalized across pages.
- Page heroes are shorter and use more consistent proportions.
- Text remains within readable widths.
- Information density improves through clearer grouping and fewer repeated sections rather than smaller text.

### U. Mobile

- Major two-column layouts collapse intentionally, not mechanically.
- Primary actions become full-width where useful.
- System previews use controlled fixed heights.
- Secondary row structures preserve labels, titles, and descriptions without becoming oversized cards.
- Subscription plans stack cleanly.

### V. Accessibility

Preserved:

- semantic headings and landmarks
- visible keyboard focus
- skip link
- keyboard-friendly navigation
- accessible search status and clear/reset behavior
- descriptive buttons/links
- proper labels on contact fields
- lightbox keyboard escape behavior
- reduced-motion handling

### W. Design consistency

The existing ivory/navy/sage/bronze design language remains. The refinement standardizes:

- page-hero proportions
- editorial row patterns
- system card hierarchy
- action hierarchy
- section spacing
- screenshot framing
- secondary-page navigation

### X. SEO risks addressed

No canonical route is renamed. No indexed page is removed. Sitemap/robots behavior is unchanged. Server-rendered system content remains intact. Existing page metadata and structured-data architecture are preserved.

### Y. Technical risks addressed

No framework migration, database change, authentication change, route rewrite, new dependency, or new JavaScript architecture is introduced. Pricing remains server-trusted through `MANAGED_SUBSCRIPTION_PRICING`.

### Z. High-impact opportunities implemented

1. Reduce repeated commercial decisions.
2. Give each page one clearer purpose.
3. Replace unnecessary cards with editorial structure.
4. Reduce screenshot/section height without hiding evidence.
5. Keep one dominant action per system catalog card.
6. Make System details the authoritative decision point for subscription plans.
7. Preserve the established navigation and technical architecture.

## Files changed for 3.4.0

- `app/templates/home.html`
- `app/templates/system_templates.html`
- `app/templates/system_template_detail.html`
- `app/templates/services.html`
- `app/templates/about.html`
- `app/templates/skills.html`
- `app/templates/experience.html`
- `app/templates/contact.html`
- `app/static/css/style.css`
- `tests/test_site.py`
- project/version documentation

No business logic file, pricing registry, database module, owner route, SEO module, or JavaScript search implementation required a behavioral rewrite.

## Acceptance contract

Do not regress 3.4.0 by reintroducing:

- repeated closing CTA panels on every page
- multiple equal-weight actions on system cards
- giant secondary-page card grids
- screenshot-led system pages
- duplicated subscription explanations on the same page
- public owner/admin navigation
- system-specific JavaScript search branches

The site should remain the same KEY CASTRO product, but with a clearer and more disciplined presentation.
