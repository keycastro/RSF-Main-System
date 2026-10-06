# RSF SECURITY AND SHARING NOTES — v1.18.229

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
- Ordinary browser actions must never be exempted from CSRF.

## AI boundary
Retell AI outbound calling is retired and must not be reintroduced unless the Founder explicitly changes the RSF non-AI service boundary. Historical AI-call rows may remain read-only for audit/history.

## Repository governance
Production source should use restricted repository access where practical. The main branch should be protected with pull-request and required-check rules. These are GitHub administrative controls, not application-code controls.
