# RSF SECURITY AND SHARING NOTES — v1.18.230

## Secrets
Never commit or expose .env files, database credentials, Render/GitHub/API tokens, OAuth secrets/tokens, WhatsApp secrets, Twilio credentials, Flask SECRET_KEY, production migration payloads, or real client private data.

## Authentication
- Passwords are stored only as secure hashes for authentication.
- Recoverable password storage/reveal is retired.
- New Founder/Partner passwords require 12–128 characters.
- Login lockout, secure cookies, CSRF, trusted hosts, CSP, HSTS, and role authorization remain required.

## External webhooks
Browser CSRF is not used to authenticate provider-to-provider callbacks.
- WhatsApp uses X-Hub-Signature-256 and the app secret.
- Twilio call callbacks use X-Twilio-Signature.
- Twilio transcription callback uses the configured callback secret plus account validation.
- Retell AI callback uses X-Retell-Signature verification.
- Ordinary browser actions must never be exempted from CSRF.

## AI boundary
Retell AI outbound calling is an approved internal RSF outreach integration. Keep RETELL_API_KEY, RETELL_AGENT_ID, and RETELL_FROM_NUMBER only in environment configuration. The Retell webhook must verify X-Retell-Signature and remain exempt only from browser CSRF; ordinary browser AI Call actions still require CSRF. This does not change the default non-AI scope of client-facing RSF development.

## Repository governance
Production source should use restricted repository access where practical. The main branch should be protected with pull-request and required-check rules. These are GitHub administrative controls, not application-code controls.
