# CURRENT v1.8.3 NAMING OVERRIDE

- Current public website remains `https://realtysystemsfoundry.onrender.com/`; requested `https://rsf.onrender.com/` is unavailable.
- Official free Partner Workspace entry: `https://partner-rsf.onrender.com/`.
- Future owned domains: `https://rsf.com/` and `https://partner.rsf.com/`.
- Do not substitute another main Render hostname without owner approval.

---

# REALTY SYSTEMS FOUNDRY WEBSITE 3.9.8 — RELEASE AUDIT

## v3.9.8 collection-handling recovery

Validated that the updater no longer uses mandatory typed-array binding for optional Render collections and directly constructs a non-empty resolved production env list after critical values are confirmed.

## v3.9.8 migration correction

The release adds secure in-memory copying of the original Render service's direct environment variables and secret files before the replacement service deploy. Required production settings are validated before service mutation. The updater does not write the Render API key or production secret values to the project, release ZIP, Git, or local `.env`.

---

# HISTORICAL REALTY SYSTEMS FOUNDRY WEBSITE 3.9.3 — RELEASE AUDIT

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

### v3.9.3 deployment-sequence hotfix
The one-run deploy workflow now waits until the Render deployment has applied the service rename before verifying `https://realtysystemsfoundry.onrender.com`. The private RSF Inbox endpoint is switched only after the new hostname is verified.


## v3.9.3 Render hostname migration correction

Production testing proved that changing the original Render service name did not reassign its existing `onrender.com` hostname. The approved target remains `https://realtysystemsfoundry.onrender.com`. v3.9.3 therefore creates a new Render service by cloning the original service configuration with Render CLI `services create --from`, verifies the new public host and the private RSF Inbox/database continuity, then records the replacement service ID for future deployments. The original service is retained as `realtysystemsfoundry-legacy` for rollback and is not deleted automatically. Public design, systems, and pricing are unchanged.

## v3.9.8 migration hotfix — empty Render collections

- Fixed the Render migration script so accounts with zero linked Environment Groups, zero direct environment variables, or zero secret files are valid inputs instead of PowerShell binding errors.
- No website design, pricing, database, or public content changes.



## v3.9.8 Render env-var key validation

The updater validates and sanitizes environment-variable keys before any Render API write. Malformed legacy keys are skipped without printing secret values. Critical production variables remain mandatory, and the original service remains the rollback until the exact new hostname and private inbox/database continuity are verified.
