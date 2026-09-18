# NEXT DEVELOPER — READ THIS FIRST

**Current version:** 2.4.0  
**Official site:** https://keycastro.onrender.com  
**Positioning:** KEY CASTRO — Custom Real Estate Systems Developer

## Current architecture

This is one Flask codebase in:

```text
C:\Users\Admin\Documents\KEY_CASTRO_WEBSITE
```

It contains both:

- the public portfolio website and contact form; and
- the private owner inbox used to manage contact-form inquiries.

There is no separate active `KEY_CASTRO_INBOX` project folder after the 2.4.0 merge.

## Public website rule

The public site remains open with no account or login requirement for Home, Projects, project case studies, Services, About, Skills, Experience, or Contact.

Do not place Admin, Inbox, Login, or Owner Dashboard links in public navigation, footer, homepage, sitemap, project pages, or other visitor-facing UI.

## Private owner inbox

The owner inbox is deployed inside the same Render Flask service and uses the same inquiry PostgreSQL database. It is intentionally not linked publicly and is excluded from the sitemap.

Direct unauthenticated access to the owner inbox returns 404. The `KEY CASTRO INBOX` desktop launcher reads the local, gitignored `.owner_inbox.json`, authenticates to a token-protected ticket endpoint, receives a short-lived signed access URL, and opens the online inbox. The browser then uses a secure Flask session.

Never commit or share `.owner_inbox.json` or `OWNER_INBOX_TOKEN`.

## Desktop launchers

- `KEY CASTRO` → opens `https://keycastro.onrender.com/`
- `KEY CASTRO INBOX` → opens the authenticated private online owner inbox

Neither launcher needs a localhost server.

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

Push both remotes explicitly, then trigger the existing Render service manually.

PythonAnywhere remains retired/deleted. Do not restore it unless the owner explicitly asks.

## Inquiry delivery

Production contact submissions are stored in the configured PostgreSQL database and appear in the private owner inbox with New, Read, Replied, and Archived states.

SMTP is only an optional notification path. Do not claim Gmail SMTP is verified until an actual authenticated delivery test succeeds.
