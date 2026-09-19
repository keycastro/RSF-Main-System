KEY CASTRO WEBSITE v3.8.2 - ONE CMD AUTO DEPLOY

This package updates the local website, preserves private configuration, runs the full test suite,
stages only approved release files, creates a release commit when needed, pushes origin and
renderdeploy, triggers the existing Render service, and verifies the live site before reporting success.

Release safety includes recovery for earlier stopped updater attempts:
- ignored release-note files no longer block deployment
- new approved Git files such as CHANGELOG.md are handled safely even when not previously tracked
- approved staged files left by a stopped updater are safely reset and restaged
- release Markdown whitespace is cleaned so Git diff --check remains a real safety gate

Success is reported only after the live health endpoint reports v3.8.2, the live How It Works page
shows the approved two-step flow, both Step 1 action buttons, no redundant final CTA, unchanged pricing, and the live Systems page
contains Student Housing Matching and Placement System with exactly three published system cards.
