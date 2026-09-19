KEY CASTRO WEBSITE v3.6.0 - ONE CMD AUTO DEPLOY (FIXED V3)

This package updates the local website, preserves private configuration, runs the full test suite,
stages only approved release files, creates a release commit when needed, pushes origin and
renderdeploy, triggers the existing Render service, and verifies the live site before reporting success.

FIXED V3 includes recovery for the earlier stopped updater attempts:
- ignored release-note files no longer block deployment
- new approved Git files such as CHANGELOG.md are handled safely even when not previously tracked
- approved staged files left by a stopped updater are safely reset and restaged
- release Markdown whitespace is cleaned so Git diff --check remains a real safety gate

Success is reported only after the live health endpoint reports v3.6.0 and the live Systems page
contains Student Housing Matching and Placement System with exactly three published system cards.
