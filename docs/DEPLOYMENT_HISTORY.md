# Deployment History — Key Castro Website

## Current state

Official host: **Render**
Official URL: **https://keycastro.onrender.com**
Render service ID: **srv-dam749e1egvs738cppq0**

## Timeline

### Local Windows build

The website was installed and used locally from:

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

Local URL:

```text
http://127.0.0.1:5050
```

### PythonAnywhere deployment — retired

The website was previously live at:

```text
https://keycastro.pythonanywhere.com
```

On 2026-09-18, the PythonAnywhere web app was deleted via API. The delete call returned HTTP **204**, indicating successful deletion of the web-app resource. Treat this host as retired.

### GitHub setup

Private primary repo:

```text
https://github.com/keycastro/key-castro-website
```

Render initially could not fetch the private repo from the CLI because the Render GitHub App did not yet have repository access.

To finish deployment through CMD, a public deployment mirror was created:

```text
https://github.com/keycastro/key-castro-render-deploy
```

### Render deployment

Render CLI version used during setup:

```text
render v2.28.0
```

Authentication succeeded with `render login`.

Workspace selected:

```text
Key Castro
```

The service was created successfully:

```text
Created service keycastro (srv-dam749e1egvs738cppq0)
```

The final public website is:

```text
https://keycastro.onrender.com
```

The service was created with auto-deploy disabled, so future changes should be explicitly deployed after pushing the public deployment mirror.

## Contact form caveat

Production is configured for Gmail SMTP, but authenticated SMTP credentials were not included in the deployment command. The site can be live while contact-form message delivery remains unverified. Complete `SMTP_USERNAME` and `SMTP_PASSWORD` securely in Render and perform a real test submission.

### 2026-09-18 — Portfolio content release 2.1.0 prepared

The existing website was updated to present Nexus Properties as a completed working portfolio project built by Key Castro. The deployment architecture was intentionally left unchanged: both GitHub repositories remain in use, Render auto-deploy remains off, and production deployment still requires an explicit Render deploy after both repositories are pushed.

This content update does not claim that Nexus Properties officially hired, paid, approved, or deployed the portfolio implementation.


### 2026-09-18 — Navigation and content clarity release 2.2.0 prepared

- Simplified the main navigation labels to Projects, Services, About, Contact.
- Reduced homepage repetition and removed duplicate project/technology messaging.
- Shortened project browsing and Nexus case-study section navigation.
- Added project breadcrumb and active case-study section state.
- Preserved every existing public route, contact workflow, SEO route, GitHub repository, and Render deployment setting.
- Production SMTP authentication remains a separate unfinished item until a real Gmail delivery test succeeds.

### 2026-09-18 — Single-codebase private owner inbox release 2.4.0

- Merged the owner inbox into the existing `KEY_CASTRO_WEBSITE` Flask codebase.
- The private inbox is now rendered online by the existing Render service and uses the existing inquiry PostgreSQL database.
- Removed the need for the old localhost inbox server on `127.0.0.1:5075`.
- Added short-lived signed owner-access tickets so the desktop launcher can open the private online inbox without exposing the bearer token in the browser URL.
- Kept the owner inbox absent from public navigation, footer, sitemap, project pages, and visitor-facing UI.
- Preserved the two existing GitHub repositories and manual Render deployment architecture.

### 2026-09-19 — Template-library and discoverability foundation 2.7.0

- Added a source-controlled reusable system-template registry and generic index/detail rendering architecture.
- Kept the public template library dormant while no real template is published.
- Added optional, backward-compatible inquiry source fields for future template-to-contact attribution.
- Added richer per-page SEO/social metadata, truthful structured data, and optional search-engine verification tags.
- Preserved the existing Flask architecture, public routes, private owner inbox, two GitHub remotes, and manual Render deployment workflow.

### 2026-09-19 — Two completed systems published through template architecture 2.8.0

- Published Property Operations Command Center and Property Inventory Hub as two independent completed systems/free standard templates.
- Reused the 2.7.0 source-controlled system-template registry and generic index/detail architecture; no competing framework or CMS was introduced.
- Added separate free-template-access and paid-customization CTAs through the existing Contact → PostgreSQL → private Inbox flow.
- Added backward-compatible `source_action` inquiry attribution so the owner can see the request type.
- Removed Nexus Properties from the current public homepage/project/sitemap presentation while retaining historical source/documentation as non-public history.
- Added truthful, source-grounded system metadata and sample-data interface previews; no client commission/adoption claim is made.
- Existing Flask, GitHub, Render, PostgreSQL, private owner authentication, and desktop-launcher architecture remain unchanged.

## 2.9.0 — Information architecture and UX organization cleanup

- Consolidated the duplicated Projects/System Templates public model into one visible **Systems** destination while preserving stable `/system-templates` URLs.
- Added explicit Home navigation and kept primary navigation to Home, Systems, Services, About, Contact.
- `/projects` now permanently redirects to `/system-templates`; duplicate Projects index content is removed from the sitemap/public hierarchy.
- Simplified homepage, system library, system detail, Services, About, Contact, and secondary Skills/Experience navigation.
- Preserved both independent published systems, Contact → PostgreSQL → private Inbox attribution, SEO, security, GitHub/Render architecture, and desktop launchers.
- Deployment should use the exact release commit SHA per the existing safe workflow to avoid serving an older branch snapshot.


## 3.0.0 — Compact premium presentation redesign

- Preserves the 2.9.0 public information architecture and the same Flask/database/security/deployment architecture.
- Reduces header, hero, page-hero, section, CTA, footer, and supporting-card vertical mass.
- Rebuilds Systems cards around concise text plus controlled previews instead of full-width giant screenshots.
- Caps system-detail hero previews and additional gallery images while retaining click-to-expand lightbox access.
- Improves desktop, tablet, and mobile content density without reducing core body readability or tap-target clarity.
- Keeps Property Operations Command Center and Property Inventory Hub fully separate.
- Keeps free standard access, paid customization, trusted contact attribution, SEO, sitemap, robots, and private Inbox behavior unchanged.


## 3.1.0 — System search + free-standard / paid-customization clarification

- Added metadata-driven, client-side filtering to the existing server-rendered Systems catalog.
- Added accessible search label, clear/reset behavior, live result status, and helpful no-match custom-development path.
- Added `search_terms` metadata while keeping search independent of system slugs in JavaScript.
- Clarified that the published standard system is free in its current form and business-specific changes are paid development.
- Preserved Contact attribution, PostgreSQL, private owner inbox, SEO, exact system URLs, 3.0.0 compact presentation, GitHub/Render architecture, and desktop launchers.

## 3.2.0 — Managed subscription + paid customization commercial model

- Retired the public free-standard-system / Free Template Access model.
- Published systems now use **Managed System Subscription** messaging and `System Subscription` inquiry attribution.
- Paid business-specific changes now use **Paid Customization**. Requirements and development price are agreed separately; the normal subscription continues while the managed system remains in use.
- No public prices, source-code ownership, unlimited-resource promises, or lifetime-access claims were added.
- Legacy `free-access` inquiry URLs are normalized server-side to the new subscription intent for backward compatibility.
- Flask architecture, real-time Systems search, canonical URLs, PostgreSQL inquiry schema, private owner Inbox, GitHub/Render architecture, and compact presentation remain unchanged.


## 3.3.0 — Managed subscription pricing

- Added approved public pricing for each existing ready-made system: **$49/month or $490/year per system**.
- Annual savings are derived from the trusted values: $49 x 12 = $588; yearly $490; savings $98/year.
- Added one pricing source of truth in `app/system_templates.py`; templates and Contact plan selection render from that source.
- Added monthly/yearly plan selection through the existing trusted Contact -> PostgreSQL -> private Inbox flow without adding checkout.
- No database schema migration is required. Plan-specific historical context is stored in the existing `source_action` text field using a trusted server-generated label.
- Browser-submitted price text is not trusted. Invalid plan keys do not become official pricing.
- Paid Customization remains separately quoted, and the normal subscription continues while the managed system remains in use.
- Preserved both independent systems, real-time search, compact 3.0 presentation, SEO architecture, private owner authentication, GitHub/Render workflow, and desktop launchers.

## 3.6.0 — Business model + Student Housing portfolio update prepared

- Preserves the established website design and Flask/Render architecture.
- Retires public software-subscription-access positioning.
- Existing systems can be customized; fully custom systems can also be requested.
- Defines only two post-build choices: **Full Handover** or **Managed by KEY CASTRO**.
- Reframes $49/month and $490/year as managed-maintenance pricing; build/customization remains separately quoted.
- Adds Student Housing Matching and Placement System as a third independent portfolio system with synthetic demo-safe screenshots and a no-client-affiliation disclaimer.
- Preserves legacy inquiry-link compatibility, trusted server-side pricing/context, private Inbox security, SEO, canonical routes, sitemap, and explicit manual Render deployment.
- This entry records a prepared release. Production should not be marked updated until the commit is pushed and Render deployment is verified.


## 3.7.0 — Master UX simplification prepared

- Reorganized and visually rebalanced the existing public website without changing the Flask architecture or business logic.
- Preserved three published systems, the two-option post-build business model, Contact/inquiry flow, private owner Inbox, SEO, and deployment architecture.
- Prepared the controlled one-run updater/deployer to require live health version 3.7.0 and exactly three published system cards before success.
- Production is not considered updated until the one-run deployment completes and live verification passes.
