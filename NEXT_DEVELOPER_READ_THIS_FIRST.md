# NEXT DEVELOPER — READ THIS FIRST

**Current version:** 2.8.0
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

## 2.8.0 published-system state

The reusable 2.7.0 foundation is now active with two real, independently inspected systems:

- `Property Operations Command Center` → `/system-templates/property-operations-command-center`
- `Property Inventory Hub` → `/system-templates/property-inventory-hub`

Both are completed systems built by Key Castro and are offered as free standard templates **by request**. Business-specific customization is paid development. They are separate applications: never mix their screenshots, features, workflows, databases, or product names.

`app/system_templates.py` remains the source-controlled registry and the generic index/detail Jinja templates remain the reusable rendering architecture. Contact attribution now includes `source_type`, `source_slug`, `source_title`, and `source_action`, allowing the private Inbox to distinguish free-template access from customization requests.

Nexus Properties was removed from the current **public** portfolio presentation in 2.8.0. Historical source/documentation may remain in the repository, but do not re-expose it publicly unless the owner explicitly changes that decision. Read `docs/PUBLISHED_SYSTEM_TEMPLATES.md` before editing current system claims.

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

## Current template strategy

The first live pattern is now proven with two real systems. Future additions must reuse the same metadata/detail/contact architecture and should be published only when the actual system, truthful content, media, SEO metadata, security review, and conversion path are ready.
