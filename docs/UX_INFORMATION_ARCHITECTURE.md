# KEY CASTRO — Information Architecture and UX Contract (2.9.0)

## Why this exists

Version 2.8.0 had two real published systems and the correct conversion architecture, but the public information architecture had started to duplicate itself. `Projects` and `System Templates` displayed the same two systems; the homepage repeated services/process/template explanations; system detail pages repeated the free-vs-custom CTA model immediately after the hero and again at the bottom; and several secondary credibility pages competed with the primary journey.

Version 2.9.0 establishes one simple public mental model without changing the Flask, database, inbox, deployment, or security architecture.

## 2.8.0 redundancy map that triggered the cleanup

| Area | Observed problem in the actual 2.8.0 source | 2.9.0 decision |
| --- | --- | --- |
| Header/footer | `Projects` and `System Templates` were separate top-level choices but both exposed the same two registry items. | One visible destination: **Systems**. |
| Homepage | Hero already explained custom systems/templates, then `WHAT I BUILD` repeated Services, `COMPLETED SYSTEMS` repeated the library, and `HOW I WORK` repeated About. | Keep only the homepage decisions: understand the offer, see systems, understand free vs paid, contact. |
| Projects index | `projects.html` rendered the same two `published_templates()` records with the same View/Request actions as the template library. | Remove duplicate index template; `/projects` becomes a 301 compatibility redirect. |
| Systems index | Hero explained free vs custom, then a second two-card model explained the same rule before the actual systems. | Keep the rule once in the hero; move directly to systems. |
| System detail | Hero had both CTAs, the next section repeated both options, the scope section repeated them again, and the final CTA repeated them a fourth time. | Keep decision CTAs at the top and bottom only; use the middle for evidence and scope. |
| Services | Service cards were organized by system/problem categories (property, rental, maintenance, dashboards), overlapping the systems/homepage. | Services now means what a business can **pay Key Castro to do**. |
| About | Approach cards, specialization, capability list, two secondary pages, and two `View projects` prompts competed for attention. | Keep identity, approach, specialization, secondary credibility links, and one Systems CTA. |
| Experience | A card linked to Projects and the page ended with another Projects CTA. | One final Systems CTA. |
| Contact | Hero instructions, a three-question coaching block, template-context explanation, textarea guidance, and button copy all repeated how to write the inquiry. | One context-aware introduction, one three-step next-process block, one focused form. |
| Mobile | The hero workflow visualization became four stacked blocks below the hero copy, making the first screen very long. | Hide that non-essential visualization on small mobile screens; preserve core actions. |

## Primary public navigation

```text
Home
Systems
Services
About
Contact
```

The brand/logo also links to Home. Home is still explicitly present in navigation for first-time and non-technical visitors.

### Secondary pages

`/skills` and `/experience` remain public/indexable credibility pages, but they are not primary navigation choices. They are linked from About and the footer.

### Legacy Projects route

`/projects` permanently redirects to `/system-templates`.

The old Projects index was removed because it duplicated the same two published systems shown by the system library. Existing `/projects/<published-system-slug>` URLs continue to redirect to the canonical `/system-templates/<slug>` detail route. Nexus remains non-public and `/projects/nexus-properties` remains 404.

## One mental model for published work

Use the word **Systems** in public navigation and visible page hierarchy.

Each published system is:

- a completed system built by Key Castro;
- available through managed system subscription access;
- customizable as paid business-specific development.

Avoid making visitors distinguish between “project,” “portfolio piece,” “system template,” and “system” as separate product categories when they refer to the same published build.

Stable SEO URLs remain `/system-templates/...`; visible labels can simply say “Systems.”

## Homepage hierarchy

1. Identity + positioning + two clear actions.
2. Published systems.
3. One concise explanation of managed subscription access vs separately priced paid customization.
4. One final custom-system CTA.

The homepage no longer repeats the Services page with service cards or the About page with a development-process section.

## Systems index hierarchy

The Systems page is the single browse destination. Each card shows only:

- free-standard-system status;
- system name;
- one-sentence purpose;
- plain-language audience;
- View System;
- Request Subscription Details.

The previous standalone free-vs-custom model block was removed from the Systems index because the page hero already explains the rule and the detail pages handle the decision in depth.

## System detail hierarchy

All systems use the same predictable sequence:

1. System identity + two primary paths.
2. Demonstration, if a real video exists.
3. System screen(s) using sample/demo data.
4. Business problem + target users.
5. Standard workflow + main features.
6. Managed subscription scope + paid customization scope.
7. Technical/build information behind a disclosure control.
8. Final two-option CTA.

The immediate post-hero duplicate access/customization block from 2.8.0 was removed. Technical details remain available without competing with the business explanation.

## Services page contract

Services means **paid work**. It is not another system catalog.

Current service groups:

- Custom System Development
- Customize an Existing KEY CASTRO System
- Workflow & Data Configuration
- Integrations, Automation & Deployment

The page should explain what a business can hire Key Castro to change or build.

## About page contract

About answers:

- who Key Castro is;
- the specialization;
- the development approach.

Skills and Experience are secondary links from About rather than primary navigation items.

## Contact page contract

The form remains the dominant action.

Generic visitors see one explanation: ask about a managed system subscription, paid customization, or a custom system.

Template-origin visitors see trusted server-side system context and request type. The page does not re-explain the entire template business model. Free-access and customization attribution continue through PostgreSQL into the private KEY CASTRO INBOX.

## Readability and mobile rules

- Primary navigation uses plain text labels and a visible Home item.
- Buttons use descriptive labels, not generic “Learn more.”
- Essential body/list text remains readable at mobile sizes.
- The non-essential hero workflow visualization is hidden on small mobile screens so the first page does not become a long vertical dump.
- Secondary technical information uses progressive disclosure.
- Footer navigation follows the same public hierarchy as the header.

## Security and SEO boundaries

This reorganization must never expose owner routes, login, inbox, tokens, or private inquiry data.

Stable system URLs, canonical metadata, structured data, sitemap coverage, and secondary credibility pages remain intact. `/projects` is intentionally excluded from the sitemap because it is now a permanent legacy redirect.


## 3.0.0 presentation layer

Version 3.0.0 does not change this information architecture. It reduces oversized screenshot treatment and excess vertical spacing while preserving the same navigation, page purposes, visitor flow, SEO routes, and free-access/customization decisions. Presentation-specific constraints now live in `docs/VISUAL_PRESENTATION_3_0.md`.
