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
