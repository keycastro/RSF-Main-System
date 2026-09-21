KEY CASTRO WEBSITE v3.8.18 - ONE CMD AUTO DEPLOY

This package updates the local website, preserves private configuration, runs the full test suite,
stages only approved release files, creates a release commit when needed, pushes origin and
renderdeploy, triggers the existing Render service, and verifies the live site before reporting success.

This release changes only the Home hero secondary CTA label from "Tell Me What You Need" to
"Create a New System". The button destination remains /contact. The existing Home cards, lower CTA
band, pricing, pages, footer, and business behavior remain unchanged.

Success is reported only after the live health endpoint reports v3.8.18 and the Home hero shows
Create a New System linking to /contact, while all existing preservation checks still pass.
