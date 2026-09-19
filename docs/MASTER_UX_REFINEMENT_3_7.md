# KEY CASTRO Website — Master UX Simplification & Visual Refinement 3.7.0

## Scope

This audit is based on the actual Flask project at v3.6.0, the live-site screenshots supplied on 2026-09-20, the active templates in `app/templates/`, the public stylesheet in `app/static/css/style.css`, the system registry in `app/system_templates.py`, the current routes in `app/routes.py`, the existing tests, and the established Render deployment workflow.

The architecture remains Flask with server-rendered Jinja templates. The public/private owner-inbox boundary, contact workflow, database logic, SEO routes, canonical URLs, and deployment provider remain unchanged.

## Master audit

### A–E. Confusing, redundant, wordy, removable, and shorten-able content

- `home.html` repeats delivery choices that are already explained on `services.html` and on each system detail page. The homepage should orient visitors, not repeat the full management model.
- `system_template_detail.html` repeats the customization CTA and repeats post-build management detail at high visual weight. The complete management explanation belongs on Services; system pages only need the essential choice, pricing, and next action.
- `about.html` uses a page introduction, a second large “Understand the work first” statement, and a separate Focus section. These are related and can be presented as one compact page story.
- `contact.html` says “Contact Me”, then “Send a short message”, then “I will read it…”. This repeats the same instruction before the form.
- System-card descriptions are longer than necessary for scanning. Card copy should communicate the difference between systems in seconds.

### F–G. What should be merged and what must remain separate

Merge:
- Home delivery explanation into one compact process summary that links to Services.
- About “How I work” and “Focus” into one compact content section.
- Services into one continuous two-stage flow: how the system starts, then who manages it.
- System-detail customization explanation into the hero/overview rather than a full separate CTA-heavy section.

Keep separate:
- The three published systems and their detail routes.
- Customize-existing vs custom-build creation paths.
- Full Handover vs Managed by KEY CASTRO post-build choices.
- Public website and private owner inbox.
- Contact source context and inquiry handling.

### H–J. Navigation

Keep primary navigation unchanged:

`Home | Systems | Services | About | Contact`

Reason: all five destinations have distinct jobs and are understandable to first-time visitors. Removing one would make the mental model less clear, not simpler.

### K. Homepage hierarchy

1. Clear one-sentence offer.
2. Primary action: View Systems. Secondary action: Contact Me.
3. Three equal system choices in one balanced desktop row.
4. One compact 3-step process summary that points to Services.

Remove the visually heavy duplicated delivery block.

### L. Page hierarchies

**Systems:** short intro → system choices → small custom-build fallback link.

**System detail:** identity + preview + primary customization action → what it solves / best for / workflow → key features + controlled extra screenshot → compact post-build choice → back to Systems.

**Services:** short intro → Stage 1: start the system → Stage 2: choose management → contact actions.

**About:** short identity → focus statement + three-step work method → View Systems.

**Contact:** direct page heading → contextual request summary when present → concise form + email alternative.

### M. Ideal visitor journey

Home → understands the offer → sees three systems → opens the closest match → understands the workflow → decides whether to customize it or request a custom build → understands Full Handover vs Managed → contacts Key Castro.

### N–P. Redundancy, content simplification, and jargon

- Keep the complete management explanation on Services.
- Keep only a compact management summary on system-detail pages.
- Keep the homepage to orientation-level wording.
- Hide system search while the catalog is very small; show it only when the catalog grows beyond six published systems.
- Use “system”, “workflow”, “hosting”, “maintenance”, “updates”, and “support” only where necessary. Avoid developer terms on public scanning surfaces.

### Q–Y. Visual and layout issues

- The desktop system grid uses a two-column layout plus a special odd-third-card centering rule, making the third system look detached and accidental.
- The homepage hero leaves a large visually empty right area while decorative background lines make that emptiness look intentional but unfinished.
- System cards use horizontal text/media splits that become too dense when the catalog grows to three items.
- Section headings are larger than their content needs and create avoidable vertical travel.
- Contact form width and shadow make the form dominate the page.
- About and Services have good content but inconsistent section mass and spacing compared with Systems.
- The stylesheet contains several generations of overlapping visual patches. A final 3.7 refinement layer should normalize active public layouts without changing backend architecture.

### Z. Mobile problems

- Cards stack acceptably, but buttons become full-width too often and increase visual mass.
- System detail sections stack into a long sequence; the 3.7 structure should reduce duplicated sections before stacking.
- Navigation remains understandable, so the mobile menu pattern should be preserved.

### AA. Accessibility

Preserve:
- skip link
- semantic navigation
- visible focus states
- form labels
- adequate tap targets
- `aria-current`
- lightbox keyboard close
- reduced-motion handling
- system-card image alt text

Improve:
- make primary/secondary action hierarchy clearer
- prevent visually redundant controls from competing
- retain readable minimum body size while reducing heading scale

### AB. Design consistency

Preserve the existing ivory, navy, sage, warm/cool system accents, typography family, restrained radii, and premium calm identity. Normalize active page widths, heading sizes, section spacing, card height, preview height, and button placement.

### AC–AD. SEO and technical risks

Do not rename public URLs. Keep canonical URLs, sitemap, robots rules, structured data, redirects, contact POST flow, inquiry source fields, owner authentication, and Render configuration intact.

The main technical risk is CSS cascade conflict from accumulated version patches. The 3.7 layer must explicitly normalize the active templates and tests must verify the final classes, routes, business wording, forms, security headers, SEO metadata, and live-version marker.

### AE. Highest-impact changes

1. Replace the 2+1 system-card layout with a balanced 3-column desktop catalog.
2. Simplify Home to orientation + systems + one short process summary.
3. Make Services one continuous two-stage decision flow.
4. Remove repeated customization/delivery mass from system detail pages.
5. Merge About content into one compact story.
6. Make Contact form visually lighter and remove repeated instructions.
7. Hide catalog search until it is genuinely useful.
8. Normalize typography, section spacing, card proportions, and responsive breakpoints site-wide.

## Implementation plan

### 1. System cards
**Current problem:** two columns plus centered odd third card creates a detached third choice. Horizontal card composition is crowded at smaller desktop widths.

**Change:** three equal vertical cards on wide desktop, two columns on medium screens, one on mobile. Use compact preview media and consistent footer/action placement.

**Files:** `home.html`, `system_templates.html`, `style.css`, `system_templates.py`.

**Expected improvement:** the three systems read as one organized portfolio immediately.

### 2. Homepage
**Current problem:** large decorative empty area and duplicated delivery explanation.

**Change:** remove the decorative split feeling, tighten hero proportions, keep two actions, show the three systems, then a compact 3-step process summary.

**Files:** `home.html`, `style.css`.

**Expected improvement:** faster understanding, less scrolling, stronger first impression.

### 3. Systems page
**Current problem:** search is unnecessary for only three systems and creates extra cognitive load.

**Change:** show search only when more than six published systems exist; keep a small custom-build fallback after the grid.

**Files:** `system_templates.html`, `style.css`; existing search JS remains as progressive enhancement for future growth.

**Expected improvement:** fewer controls and faster selection now without removing future scalability.

### 4. System detail pages
**Current problem:** duplicated customization CTA, multiple full sections, and a large post-build decision area produce long pages.

**Change:** keep one primary hero CTA, combine overview + audience + workflow, show features and controlled secondary screenshot, move project note into progressive disclosure, and reduce delivery to two compact choices with one managed CTA.

**Files:** `system_template_detail.html`, `style.css`.

**Expected improvement:** visitors understand the system faster and reach the next action with less scrolling.

### 5. Services
**Current problem:** the correct business model is split into visually separate large blocks.

**Change:** present it as two simple stages in one continuous page: Start the system, then Choose who manages it.

**Files:** `services.html`, `style.css`.

**Expected improvement:** the business model becomes obvious without decoding multiple sections.

### 6. About
**Current problem:** related information is separated into multiple large sections.

**Change:** one compact section containing focus + three-step working method + one systems link.

**Files:** `about.html`, `style.css`.

**Expected improvement:** stronger personal positioning with less page length.

### 7. Contact
**Current problem:** repeated instructions and a visually dominant form.

**Change:** direct heading, concise response note/email alternative, narrower lighter form, preserved contextual request summary and backend flow.

**Files:** `contact.html`, `style.css`.

**Expected improvement:** lower friction and clearer next step.

### 8. Release safety

Update tests, version metadata, changelog, release audit, deployment expected version, and live verification. Keep secrets out of the release package. Preserve the existing local `.env`, owner-inbox token, Git repository, and Render configuration during installation.
