# KEY CASTRO 3.5.2 — Site-wide page-top refinement

## Scope

Focused layout refinement only. No business logic, pricing, search, contact, authentication, routes, redirects, SEO model, private Inbox, or system-card identity logic is changed.

## Audit findings

The current 3.5.1 public pages use compact copy, but shared top spacing still creates unnecessary vertical travel. The main source is the combination of `page-hero-simple` bottom padding and the first content section's top padding. The system-detail hero and 404 page also retain more vertical space than their content requires.

Pages reviewed:

- Home — useful hero, but desktop vertical travel can be reduced moderately.
- Systems — title/support copy sits too far from search and system choices.
- Services — title sits too far from the two service choices.
- About — title sits too far from the first About content.
- Contact — title sits too far from the form/request context.
- Both system detail pages — title, preview, and first information section can connect more tightly.
- 404 — error presentation uses more vertical height than necessary.
- `/skills` and `/experience` remain 301 redirects to About; `/projects` remains a 301 redirect to Systems.

## Implementation

The update uses shared CSS rules instead of page-by-page template patches:

- tighter `page-hero-simple` vertical padding
- tighter spacing between a simple page hero and its immediately following section
- moderate Home hero tightening without flattening its hierarchy
- tighter system-detail hero spacing and first-section connection
- smaller 404 vertical field
- responsive adjustments for tablet and mobile

Whitespace remains intentional; headings, tap targets, card identities, and readable text sizes are preserved.
