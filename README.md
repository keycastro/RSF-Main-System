# KEY CASTRO — Professional Website

> **Developer handoff:** New maintainers should read [`NEXT_DEVELOPER_READ_THIS_FIRST.md`](NEXT_DEVELOPER_READ_THIS_FIRST.md), [`PROJECT_STATE.json`](PROJECT_STATE.json), and [`SECURITY_AND_SHARING_NOTES.md`](SECURITY_AND_SHARING_NOTES.md) before changing code, deployment, domains, or hosting.


**Version:** 2.1.0 — Completed Nexus Portfolio Project Update  
**Local URL:** `http://127.0.0.1:5050`  
**Health endpoint:** `http://127.0.0.1:5050/system/health`

This is a real Flask website that runs locally on Windows first and is structured so the same website can later be published online.

## Professional identity

**Key Castro — Custom Real Estate Systems Developer**

> I build custom web applications and business systems for real estate and rental-property operations.

## Pages

- Home
- About
- Services
- Work / Projects
- Nexus Properties case study
- Skills & Technology
- Experience
- Contact

The top navigation intentionally stays simple: **Work · Services · About · Discuss a Project**.

## Daily local use

Do not open CMD for normal use.

```text
Desktop → KEY CASTRO
```

The launcher:

```text
checks http://127.0.0.1:5050/system/health
→ avoids a duplicate server
→ starts Flask hidden if needed
→ waits for the health check
→ opens the browser
```

## Local contact form

Local test submissions are stored at:

```text
instance/contact_messages.jsonl
```

Production contact delivery uses SMTP configuration from environment variables. See `docs/DEPLOYMENT_NOTES.md`.

## Public details

Add only verified values to the local `.env` when needed:

```text
CONTACT_EMAIL=
LINKEDIN_URL=
GITHUB_URL=
YOUTUBE_URL=
FACEBOOK_URL=
```

Never put passwords, API keys, private IDs, confidential client data, or database credentials into public templates or repositories.

## Tests

From the installed project:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Production

The deployable entry point is:

```text
wsgi:app
```

Read `docs/DEPLOYMENT_NOTES.md` before publishing. Version 2.1.0 continues to require the public URL, trusted hosts, verified contact email, and production mail delivery to be configured before a Production start succeeds.
