# RSF v1.18.230 — RELEASE AUDIT

## Scope
Founder-approved communication integration restoration and provider-label refinement.

## Changes
- Restored the active Retell AI outbound-call implementation without restoring the retired password vault.
- Restored Prospect AI Call and retained locked AI Call shells in contexts where AI Call is not available.
- Retell server-to-server webhook remains outside browser CSRF and verifies X-Retell-Signature.
- Added the final communication mapping: AI Call → Retell AI; Manual Call → Twilio; Google Meet → Google Meet; Email → Gmail; WhatsApp → WhatsApp Business.
- Added small muted provider names under each communication button so the provider is secondary to the action.
- Fixed Prospect Notes timeline argument ordering left by the prior AI-call removal.
- Added Retell AI to Integration Usage & Billing using RSF-recorded AI-call usage; provider billing cost remains Not available unless a trustworthy provider billing source is added.
- Renamed visible integration service labels to Gmail, Google Meet, WhatsApp Business, Twilio, and Retell AI.
- Retained hash-only password authentication, migration 43, webhook security hardening, and retired ready-made-system pricing cleanup.

## Release verification required
- Full regression suite passes.
- Account Security Audit passes.
- Maximum Audit passes.
- Partner Workspace URL/browser check passes.
- Render build/deploy succeeds on the exact merged main commit.
- /system/health reports version 1.18.230.
- No post-deploy error/warning logs.

## Runtime setup note
Retell AI Call is enabled only when RETELL_API_KEY, RETELL_AGENT_ID, and RETELL_FROM_NUMBER are configured in the Render environment. If they are absent, the UI remains safely unavailable instead of starting a call.
