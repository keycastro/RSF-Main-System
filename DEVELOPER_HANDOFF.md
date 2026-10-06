# RSF Developer Handoff — Current

**Current version:** 1.18.229
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
- No AI development/calling is part of the current RSF service boundary.

## Security rules

- Browser/session POST actions use CSRF protection.
- External provider callbacks use provider signature/secret validation and are exempt only from browser CSRF.
- Retell AI outbound calling is retired. Historical AI-call rows may remain read-only for business history.
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
