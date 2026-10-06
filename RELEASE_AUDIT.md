# RSF v1.18.229 — RELEASE AUDIT

## Scope
Security and maintenance hardening after the October 6, 2026 deep audit.

## Changes
- Fixed browser-CSRF handling for WhatsApp and Twilio provider callbacks while keeping browser writes CSRF-protected.
- Retired active Retell AI outbound calling: UI, start-call route, webhook, config, and SDK dependency removed.
- Preserved historical ai_sales_calls records as read-only business history.
- Retired recoverable password storage and password reveal/copy behavior.
- Added migration 43 to delete the encrypted password-vault table without deleting accounts or business data.
- New Founder/Partner passwords require 12–128 characters.
- Removed the retired USD 199 existing-system pricing source/context.
- Updated tests and GitHub Actions to the current version/business model.

## Required production verification
- GitHub checks pass.
- Render deploy uses the merged main commit.
- /system/health returns status ok and version 1.18.229.
- Production startup succeeds.
- No post-deploy error/warning/critical logs.
- Private workspace remains authenticated.
- Integration Usage & Billing loads successfully.

## Governance follow-up
Repository visibility and main-branch protection are GitHub administrative settings and must be configured in repository settings if the connected GitHub integration lacks administration permission.
