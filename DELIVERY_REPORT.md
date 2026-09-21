# DELIVERY REPORT — REALTY SYSTEMS FOUNDRY 3.9.2

## Approved change
The existing Render-hosted website is migrated from the former `keycastro.onrender.com` identity to:

**https://realtysystemsfoundry.onrender.com**

This is a rename of the existing Render service, not a second website or a new hosting stack. The service ID, GitHub repositories, database, public design, three published systems, and approved pricing remain unchanged.

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

### v3.9.2 deployment-sequence hotfix
The one-run deploy workflow now waits until the Render deployment has applied the service rename before verifying `https://realtysystemsfoundry.onrender.com`. The private RSF Inbox endpoint is switched only after the new hostname is verified.
