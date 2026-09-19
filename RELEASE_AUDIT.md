# KEY CASTRO WEBSITE 3.8.2 — RELEASE AUDIT

- Baseline inspected: v3.8.1.
- Scope limited to the approved How It Works buttons/final-CTA cleanup and direct dependencies.
- No unrelated visual redesign, route change, business-model change, page edit, or refactor.
- Final How It Works flow remains exactly Step 1 **Tell me what you need** → Step 2 **Choose who manages it**.
- Step 1 now has balanced **View Systems** and **Request a System** buttons.
- The redundant final **Want to get started?** CTA is removed.
- Pricing remains **$49/month** or **$490/year**.
- Release ZIP must exclude `.env`, `.owner_inbox.json`, `.git`, databases, logs, caches, backups, tokens, and private runtime data.
- Live deployment is valid only after production verification confirms version 3.8.2, the exact How It Works content, and all three published systems.
