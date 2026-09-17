# KEY CASTRO — Professional Website

**Version:** 2.0.0 — Public Launch Edition  
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

Read `docs/DEPLOYMENT_NOTES.md` before publishing. Version 2.0.0 intentionally requires the public URL, trusted hosts, verified contact email, and production mail delivery to be configured before a Production start succeeds.
