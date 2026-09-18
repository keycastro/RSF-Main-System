# NEXT DEVELOPER — READ THIS FIRST

**Current version:** 2.7.0
**Official site:** https://keycastro.onrender.com
**Positioning:** KEY CASTRO — Custom Real Estate Systems Developer

## Read first

Before changing the website, read:

1. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md` (local/private roadmap)
2. `docs/FUTURE_TEMPLATE_LIBRARY_ROADMAP.md` (local/private roadmap)
3. `docs/TEMPLATE_LIBRARY_FOUNDATION.md`
4. `PROJECT_STATE.json`
5. `SECURITY_AND_SHARING_NOTES.md`
6. `docs/DEPLOYMENT_HISTORY.md`
7. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`

## Current architecture

This is one Flask codebase in:

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

It contains the public portfolio/contact flow and the private owner inbox. Do not split them into separate active projects.

## 2.7.0 future-product foundation

The codebase now contains a dormant reusable foundation for future real-estate system templates:

- `app/system_templates.py` — source-controlled metadata registry
- `/system-templates` and `/system-templates/<slug>` — reserved stable routes
- generic Jinja index/detail templates
- conditional navigation/footer visibility only when a real template is published
- future template URLs excluded from sitemap while no published template exists
- optional inquiry source fields (`source_type`, `source_slug`, `source_title`)
- trusted `/contact?template=<slug>` conversion context
- owner-inbox display for template interest when present
- expanded SEO/social metadata and truthful structured data
- optional Search Console/Bing verification meta tags

**There are intentionally no published templates in the 2.7.0 foundation release. Do not create placeholder content merely to activate the library.**

## Public website rule

Home, Projects, project case studies, Services, About, Skills, Experience, and Contact remain public with no login.

Do not place Admin, Inbox, Login, or Owner Dashboard links in any visitor-facing UI or sitemap.

## Private owner inbox

The owner inbox is deployed inside the same Render Flask service and uses the same PostgreSQL inquiry database. It is not linked publicly and is excluded from the sitemap.

Unauthenticated direct access returns 404. The `KEY CASTRO INBOX` desktop launcher reads the local, gitignored `.owner_inbox.json`, exchanges its bearer token for a short-lived signed access URL, and opens a secure Flask owner session.

Never commit or share `.owner_inbox.json`, `OWNER_INBOX_TOKEN`, `DATABASE_URL`, `.env`, tokens, or inquiry data.

## Hosting and deployment

Render remains the official host.

```text
Service: keycastro
Service ID: srv-dam749e1egvs738cppq0
Health: /system/health
Auto-deploy: false
```

GitHub remains:

```text
Private primary: https://github.com/keycastro/key-castro-website
Public Render mirror: https://github.com/keycastro/key-castro-render-deploy
```

Push both remotes explicitly, then trigger the existing Render service manually. PythonAnywhere remains retired.

## First flagship strategy

The recommended first template is a **Property Maintenance Management System**. Build only one flagship first and prove the complete path from useful content/demo to Contact source context to private Inbox before starting a second template.
