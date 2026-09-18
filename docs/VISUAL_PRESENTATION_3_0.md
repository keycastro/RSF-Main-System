# KEY CASTRO — Visual Presentation Contract (3.0.0)

## Why 3.0.0 exists

The 2.9.0 information architecture solved duplicate destinations and clarified the visitor journey, but the live presentation still used oversized screenshot containers and generous legacy spacing from earlier portfolio layouts. On a normal desktop, a system screenshot could occupy hundreds of vertical pixels before the visitor reached the title, audience, and action. The result felt more like a screenshot gallery than a compact software consultancy showcase.

## Problems found in the actual 2.9.0 source

- `--header:82px` plus a 43px brand mark made the sticky header visually heavy.
- `.hero` used `min-height:calc(100vh - var(--header))` with ~200px of vertical padding, delaying meaningful content below the first viewport.
- `.section` used 104px top/bottom padding globally, multiplying empty vertical travel across every page.
- `.page-hero` used 96px/82px padding and headings up to 66px even on simple secondary pages.
- `.template-card-image img` and `.system-showcase-image img` used a full-width 16:10 ratio, making each screenshot the largest object in the card.
- Systems cards placed the screenshot before the system name, purpose, audience, and CTA.
- `.case-cover img` also used a large 16:10 presentation in a 50/50 hero, which competed with system identity.
- `.template-gallery-grid` showed additional screenshots at their natural 16:10 ratio rather than as controlled previews.
- `.cta-panel` used 60px+ internal padding; Services/About cards and the footer also retained large minimum heights and spacing from older visual systems.

## 3.0.0 design rules

### Screenshot hierarchy

Screenshots are evidence, not the page itself.

- Catalog/home previews are intentionally cropped and height-controlled.
- The system name/purpose/audience appears before or beside the preview, never buried underneath a giant image.
- The first detail screenshot is a compact preview capped to a comfortable height.
- Additional screenshots use a controlled gallery.
- Full-resolution inspection remains available through the existing lightbox.

### Density

- Premium whitespace is preserved around decisions and groups.
- Global section padding is reduced.
- Header, page heroes, CTAs, footer, service cards, and About cards use shorter proportions.
- Body copy remains readable; no essential label or action is made tiny to create density.

### System catalog

The two systems remain two independent applications. Each catalog card communicates, in order:

1. Free standard system status
2. System name
3. One-sentence purpose
4. Audience
5. Compact preview
6. View System / Request Free Access actions

### Detail pages

Predictable sequence remains:

1. Identity + short explanation + top decisions
2. Compact primary preview
3. Business problem + users
4. Workflow + features
5. Controlled screenshot gallery
6. Free standard scope + paid customization
7. Technical disclosure
8. Final decision CTA

### Mobile

- Decorative homepage brief is removed on small screens.
- System card order becomes information → compact preview → actions.
- Image previews use fixed compact heights rather than natural screenshot height.
- Buttons remain full-width where that improves tapping and clarity.

## Do not regress

Do not restore full-width natural-ratio screenshots inside catalog cards, full-viewport homepage hero height, 100px+ default section padding, or giant screenshot-led system cards. The site should remain a professional business-system showcase, not an image gallery.
