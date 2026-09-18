# KEY CASTRO WEBSITE — SYSTEM SEARCH + ACCESS MODEL 3.1.0

Version 3.1.0 extends the existing 3.0.0 compact premium production site without rebuilding or changing its Flask/PostgreSQL/Render architecture.

## Main changes

- Added a compact **Find a system** control to the Systems page.
- Search filters the existing server-rendered system cards instantly without a page reload.
- Search is metadata-driven through `SystemTemplate.search_text` and optional `search_terms`, so future systems inherit the behavior without slug-specific JavaScript.
- Added accessible label, keyboard behavior, Escape/clear reset, visible focus, polite result-count status, and progressive enhancement.
- Added a commercially useful no-match state that links to the existing generic custom-system Contact path instead of ending at “no results.”
- Clarified that **free** means the existing standard system in its current form.
- Clarified that business-specific modifications and additional development are **paid custom development**.
- Updated system detail and contextual Contact wording without repeating the same sales explanation across every card.

## Preserved

- Compact 3.0.0 presentation and screenshot controls.
- Home · Systems · Services · About · Contact information architecture.
- Property Operations Command Center and Property Inventory Hub as separate systems.
- Free-access, customization, and generic Contact flows.
- Trusted server-side system attribution, PostgreSQL inquiry storage, and private KEY CASTRO INBOX.
- SEO, canonical routes, sitemap, robots, structured data, Flask architecture, GitHub repositories, Render service, and desktop launchers.

See `docs/SYSTEM_SEARCH_AND_ACCESS_MODEL_3_1.md`.
