# KEY CASTRO WEBSITE 3.8.3 — RELEASE AUDIT

- Baseline inspected: v3.8.2 from the user-provided website ZIP.
- Scope limited to the approved **About** expansion and footer tagline replacement, plus direct dependencies.
- About now emphasizes common operational problems: too many tools/subscriptions, manual work, scattered information, missed follow-ups, limited automation, and generic-software limitations.
- Automation is a dedicated highlighted About section with rule-based examples.
- Subscription-cost wording is intentionally qualified: a custom system **may reduce dependence** on multiple paid tools; it does not claim custom software is always cheaper.
- Footer tagline is exactly **“Better systems for complex business needs.”**
- No Home, Systems, How It Works, Contact, system-detail, pricing, route, backend, database, owner-Inbox, or business-model change.
- About-specific CSS is scoped to `.about-*` classes to avoid unrelated page changes.
- Release ZIP must exclude `.env`, `.owner_inbox.json`, `.git`, databases, logs, caches, backups, tokens, and private runtime data.
- Live deployment is valid only after production verification confirms version 3.8.3, the new About content/tagline, the unchanged approved How It Works content, and all three published systems.
