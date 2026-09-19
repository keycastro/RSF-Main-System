# CHANGELOG

## 3.8.2 — How It Works action clarity

- Replaced the Step 1 **View Systems** text link with a clear button-style action.
- Added a matching **Request a System** button to the **Build a new system** card; it opens Contact with the existing custom-build context.
- Removed the redundant final **Want to get started?** CTA block.
- Preserved the two-step flow, management choices, pricing, route, visual identity, and every unrelated page/feature.

## 3.8.1 — How It Works redundancy cleanup

- Changed the existing-system sentence to: **“I can adapt one of my existing systems to fit your business.”**
- Removed the redundant **“I build the system.”** middle step from How It Works.
- Renumbered **“Choose who manages it.”** from Step 3 to Step 2.
- Preserved the final **Want to get started?** CTA, both management choices, pricing, route, visual design, and all other pages.

## 3.8.0 — Human clarity and older-user-friendly simplification

- Rewrote the public experience for first-time, non-technical, older, and basic-English visitors.
- Renamed the visible **Services** navigation label to **How It Works** while preserving the canonical `/services` route.
- Replaced abstract process wording with concrete actions: **Tell me what you need → I build the system → choose who manages it**.
- Simplified system cards and removed nonessential category micro-labels and repeated “See All Systems” links.
- Simplified system-detail pages so they explain the system first and no longer repeat the full post-build management model.
- Kept the complete management explanation on **How It Works** with only two choices: **You Manage It** or **I Manage It**.
- Removed public-facing secondary jargon labels such as “Full handover” and “Managed by KEY CASTRO” from the choice cards while preserving those terms internally for business logic and documentation.
- Increased everyday text and control sizes for older-user readability without changing the ivory/navy/sage brand.
- Preserved all three systems, pricing, contact/database flow, private owner Inbox, SEO, security boundaries, and deployment architecture.
- Expanded regression coverage for beginner/older-user public-copy rules.

## 3.7.0 — Master UX simplification and visual refinement

- Performed the complete site-wide UX, content, information-architecture, visual, responsive, accessibility, SEO, and release audit.
- Preserved the existing Flask architecture, brand identity, five-item navigation, business model, contact flow, owner Inbox, and security boundary.
- Rebalanced Home into a compact orientation page and removed repeated delivery information.
- Changed Home and Systems to a balanced three-column system grid on desktop; removed the old centered odd third-card composition.
- Hid the Systems search control for the current three-item catalog while retaining metadata-driven search for future larger catalogs.
- Simplified Services into one two-stage decision flow and kept exactly two post-build management options.
- Merged and shortened About content; tightened Contact content and form composition.
- Simplified system detail pages with controlled media, progressive disclosure, and compact delivery rows.
- Updated public copy to shorter, internationally understandable English.
- Updated tests to protect the new 3.7.0 composition and retained backend/security behavior.

## 3.6.0 — Business model + Student Housing portfolio update

- Preserved the existing KEY CASTRO visual design, Flask architecture, navigation, SEO foundation, contact flow, and private owner Inbox.
- Replaced the public software-access subscription model with the current service model:
  - Customize Existing System or Custom System Build.
  - After delivery: Full Handover or Managed by KEY CASTRO only.
- Reframed $49/month and $490/year as managed-maintenance pricing; system build/customization remains separately quoted.
- Added Student Housing Matching and Placement System as the third independent published system.
- Added synthetic demo-safe Student Housing screenshots and truthful independent-portfolio wording.
- Added trusted inquiry intents for customization, custom build, full handover, managed service, monthly maintenance, and yearly maintenance.
- Kept legacy `subscribe` and `free-access` inquiry links compatible by normalizing them to the current managed-service flow.
- Updated project state, handoff, current product plan, published-system documentation, and deployment history.
- Updated local installer documentation copying so current handoff/state files travel with the installed project.
- Expanded automated regression coverage for the new commercial model, Student Housing system, sitemap, SEO, inquiry trust boundary, and public wording.
- Added controlled one-run release automation: local update and tests now continue through approved Git pushes, explicit Render deployment, and live production verification before success is reported.
