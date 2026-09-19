# KEY CASTRO WEBSITE 3.8.6 — RELEASE AUDIT

- Baseline inspected: v3.8.5 from the user-provided authoritative website ZIP.
- Scope limited to redesigning only the About top profile organization, plus direct dependencies; the approved portrait asset itself is unchanged.
- The existing approved About problem/automation/subscription-value messaging remains unchanged.
- The existing approved portrait asset is preserved byte-for-byte; no AI regeneration, facial alteration, image replacement, or unrelated content redesign was performed in this update.
- Moved the existing professional title **Custom Business App Developer & Automation Specialist** from the left intro to directly below the portrait so the photo and title form one intentional profile block.
- Portrait/profile styling is scoped to `.about-*` selectors and uses the existing ivory/navy/sage design tokens.
- No Home, Systems, How It Works, Contact, footer, pricing, route, backend, database, owner-Inbox, published-system, or business-model change.
- Release ZIP must exclude `.env`, `.owner_inbox.json`, `.git`, databases, logs, caches, backups, tokens, and private runtime data.
- Live deployment is valid only after production verification confirms version 3.8.6, the revised About top profile block and unchanged portrait asset, the unchanged approved About content/footer tagline, the approved How It Works content, and all three published systems.
