# KEY CASTRO WEBSITE 3.8.9 — RELEASE AUDIT

- Baseline inspected: v3.8.8 from the user-provided authoritative website ZIP.
- Scope is a **content and pricing update only — not a redesign**.
- Public design files are unchanged; `app/static/css/style.css` is byte-for-byte identical to the v3.8.8 baseline.
- How It Works keeps the same page structure, two steps, two management-choice cards, buttons, classes, and responsive behavior.
- Managed maintenance is now **$39/month or $390/year** from the existing trusted pricing source.
- Build/customization remains **Custom Quote**.
- Maintenance wording now makes clear that it keeps the current system running and does not include new features or later workflow/function changes.
- Future improvements are shown as **Minor System Upgrade — $79**, **Major System Upgrade — $149**, and **very large expansion / new system — Custom Quote**.
- No Home, Systems, About, Contact, navigation, footer, route, form, database, owner-Inbox, published-system, or authentication change.
- Release ZIP must exclude `.env`, `.owner_inbox.json`, `.git`, databases, logs, caches, backups, tokens, and private runtime data.
- Live deployment is valid only after production verification confirms version 3.8.9 and the approved pricing/service wording while all preserved site checks still pass.
