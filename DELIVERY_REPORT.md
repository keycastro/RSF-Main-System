# DELIVERY REPORT — REALTY SYSTEMS FOUNDRY 3.9.8

## v3.9.8 resume-safe completion

The previous run successfully created and deployed the exact `realtysystemsfoundry` Render service and confirmed the private RSF Inbox token plus existing database continuity. It stopped only when Git's whitespace preflight found formatting issues in release files. v3.9.8 detects that already healthy replacement service, skips unnecessary recreation/API-key migration work, cleans the source-control whitespace issues, and resumes at the commit/push/exact-deploy/final-verification stage.

# DELIVERY REPORT — REALTY SYSTEMS FOUNDRY 3.9.8

## v3.9.8 collection-handling recovery

The previous run successfully resolved the Render API key, RSF Inbox token, contact email, Render Postgres connection, and malformed legacy env key filtering, but Windows PowerShell 5.1 stopped on an empty intermediate collection. v3.9.8 removes that mandatory collection binding path and validates the final production payload before Render changes.

## v3.9.8 Render migration fix

The v3.9.3 replacement service was created successfully but its deploy failed because the CLI clone did not copy the production environment variables required by the Flask production configuration. v3.9.8 securely reads those existing values from the original service via the official Render API, copies them to the replacement before the verified deploy, preserves the private RSF Inbox token/database connection, and keeps the original service as rollback until the new hostname is fully verified.

---

# HISTORICAL DELIVERY REPORT — REALTY SYSTEMS FOUNDRY 3.9.3

## Approved change
The existing Render-hosted website is migrated from the former `keycastro.onrender.com` identity to:

**https://realtysystemsfoundry.onrender.com**

This migration creates a replacement Render web service by cloning the existing service configuration because production testing showed that renaming the original service did not reassign its `onrender.com` hostname. GitHub repositories, database connection, public design, three published systems, and approved pricing remain unchanged. The original Render service is retained temporarily as a rollback service.

## Local integrations
- `REALTY SYSTEMS FOUNDRY` desktop launcher opens the new Render URL.
- `RSF INBOX` keeps its private token and automatically changes only its API base to the new host after Render confirms the hostname is reachable.
- Local project folder remains `C:\Users\Admin\Documents\REALTY_SYSTEMS_FOUNDRY`.

## Production URL handling
The application now recognizes Render's built-in external URL/hostname variables during the migration, preventing a stale former Render URL from controlling canonical links or trusted-host validation. A future paid/custom `.com` domain can still override the Render URL through `PUBLIC_BASE_URL`.

## Pricing preserved
- Existing Ready-Built System: **$199 one-time**
- Optional managed care: **$39/month or $390/year**
- Minor Upgrade: **$79**
- Major Upgrade: **$149**
- New System / Large Expansion: **Price by Agreement**

### v3.9.3 deployment-sequence hotfix
The one-run deploy workflow now waits until the Render deployment has applied the service rename before verifying `https://realtysystemsfoundry.onrender.com`. The private RSF Inbox endpoint is switched only after the new hostname is verified.


## v3.9.3 Render hostname migration correction

Production testing proved that changing the original Render service name did not reassign its existing `onrender.com` hostname. The approved target remains `https://realtysystemsfoundry.onrender.com`. v3.9.3 therefore creates a new Render service by cloning the original service configuration with Render CLI `services create --from`, verifies the new public host and the private RSF Inbox/database continuity, then records the replacement service ID for future deployments. The original service is retained as `realtysystemsfoundry-legacy` for rollback and is not deleted automatically. Public design, systems, and pricing are unchanged.

## v3.9.8 migration hotfix — empty Render collections

- Fixed the Render migration script so accounts with zero linked Environment Groups, zero direct environment variables, or zero secret files are valid inputs instead of PowerShell binding errors.
- No website design, pricing, database, or public content changes.



## v3.9.8 Render env-var key validation

The updater validates and sanitizes environment-variable keys before any Render API write. Malformed legacy keys are skipped without printing secret values. Critical production variables remain mandatory, and the original service remains the rollback until the exact new hostname and private inbox/database continuity are verified.
