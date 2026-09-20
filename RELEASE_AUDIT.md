# KEY CASTRO WEBSITE 3.8.11 — RELEASE AUDIT

- Baseline inspected: user-provided authoritative v3.8.9 project ZIP.
- Scope: **How It Works Step 2 clarity and organization only**.
- Step 1, Home, Systems, About, Contact, navigation, footer, backend, routes, forms, database, authentication, and published systems are unchanged.
- Exactly two management choices remain: **You Manage It** and **I Manage It**.
- Approved maintenance price remains **$39/month or $390/year**.
- Maintenance information is now grouped into **You handle**, **Maintenance can include**, and **Maintenance does not include** for faster scanning.
- **Need changes later?** remains connected to the management section through three clear upgrade cards: **$79 Minor**, **$149 Major**, and **Custom Quote New System / Large Expansion**.
- Upgrades remain separate from maintenance and remain available later whether the client self-manages or Key manages the system.
- CSS changes are appended and scoped under `#management-options` only.
- Release ZIP must exclude `.env`, `.owner_inbox.json`, `.git`, databases, logs, caches, backups, tokens, and private runtime data.
- Live deployment is valid only after production verification confirms version 3.8.11 and the approved Step 2 wording/structure while preserved site checks still pass.
