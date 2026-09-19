# KEY CASTRO WEBSITE 3.8.4 — RELEASE AUDIT

- Baseline inspected: v3.8.3 from the user-provided authoritative website ZIP.
- Scope limited to adding the supplied professional portrait to the **About page only**, plus direct dependencies.
- The existing About text and approved problem/automation/subscription-value messaging remain unchanged.
- Portrait source is the user-supplied image; no AI regeneration, facial alteration, background replacement, or aggressive crop was performed.
- Portrait styling is scoped to `.about-*` selectors and uses the existing ivory/navy/sage design tokens.
- No Home, Systems, How It Works, Contact, footer, pricing, route, backend, database, owner-Inbox, published-system, or business-model change.
- Release ZIP must exclude `.env`, `.owner_inbox.json`, `.git`, databases, logs, caches, backups, tokens, and private runtime data.
- Live deployment is valid only after production verification confirms version 3.8.4, the About portrait and asset, the unchanged approved About content/footer tagline, the approved How It Works content, and all three published systems.
