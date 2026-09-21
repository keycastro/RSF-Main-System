# REALTY SYSTEMS FOUNDRY WEBSITE 3.9.2 — RELEASE AUDIT

## Scope
- Rename the existing Render web service to **realtysystemsfoundry**.
- Target public Render URL: `https://realtysystemsfoundry.onrender.com`.
- Preserve service ID, GitHub repositories, database, design, systems, and approved pricing.
- Update the main desktop website launcher and private RSF Inbox endpoint to the new Render host.
- Update SEO/canonical configuration and trusted-host handling for the renamed Render service.

## Safety
- The updater uses the existing Render service ID; it does **not** create a second hosting service.
- If Render rejects the exact service name, deployment stops before Git staging/push.
- The private `.owner_inbox.json` token is preserved; only its `api_base` is changed after the new hostname responds successfully.
- Production configuration can use Render's `RENDER_EXTERNAL_URL` and `RENDER_EXTERNAL_HOSTNAME` so a stale former Render URL does not break canonical URLs or host validation after the rename.

## Business rules preserved
- Ready-built system: **$199 one-time**
- Self-managed: **$0/month management fee**
- Optional managed care: **$39/month or $390/year**
- Minor Upgrade: **$79**
- Major Upgrade: **$149**
- New System / Large Expansion: **Price by Agreement**

## Security
Safe release ZIP excludes `.env`, `.owner_inbox.json`, `.git`, `.venv`, backups, logs, databases, and cache files. Full local tests must pass before Git push/deployment, and the new live hostname must pass final verification.

### v3.9.2 deployment-sequence hotfix
The one-run deploy workflow now waits until the Render deployment has applied the service rename before verifying `https://realtysystemsfoundry.onrender.com`. The private RSF Inbox endpoint is switched only after the new hostname is verified.
