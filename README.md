# RSF Main System — Current Authoritative State

**Current version:** 1.18.230
**Repository:** keycastro/RSF-Main-System
**Production:** https://realtysystemsfoundry.onrender.com
**Render service:** realtysystemsfoundry
**Render branch:** main
**Auto Deploy:** OFF
**Framework:** Flask
**Production database:** PostgreSQL on Render

## Current business model

RSF builds custom business systems for real-estate and property-management businesses.

- Public website does not sell ready-made systems.
- Existing public systems are portfolio/examples only.
- Limited Free Custom System Build program: November 1, 2026 through March 31, 2027, subject to RSF project acceptance.
- After the beginning-stage free period, custom development moves toward Price by Agreement.
- Paid RSF post-delivery support is optional and Price by Agreement.
- Major changes, large expansions, major features, and major integrations are Price by Agreement.
- Client-facing RSF development remains non-AI by default; the private RSF workspace intentionally uses Retell AI for the Founder-approved AI Call outreach feature.

## Security rules

- Browser/session POST actions use CSRF protection.
- External provider callbacks use provider signature/secret validation and are exempt only from browser CSRF.
- Retell AI outbound calling is active as an internal RSF outreach integration when RETELL_API_KEY, RETELL_AGENT_ID, and RETELL_FROM_NUMBER are configured. Historical and new AI-call records use ai_sales_calls.
- Password authentication is hash-only. Recoverable encrypted password copies are retired and removed by migration 43.
- New Founder/Partner passwords must be 12–128 characters.
- Secrets remain in environment configuration and never in Git.

## Release workflow

1. Change source on a controlled branch.
2. Run compile plus full regression tests.
3. Merge only after checks pass.
4. Manually trigger Render deployment because Auto Deploy is OFF.
5. Verify exact deployed commit, /system/health, startup, and logs.
6. Update RSF SYSTEM DEVELOPMENT DOCUMENTATION after verified production release.

Historical release notes are not authoritative when they conflict with this current state.
