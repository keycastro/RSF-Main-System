# SECURITY AND SHARING NOTES — v3.9.8

The Render hostname migration may ask for a Render API key using hidden PowerShell input. The updater uses that key only in the running process to read/copy production configuration. It must never be printed, saved into `.env`, `.owner_inbox.json`, project files, Git, logs, or the release ZIP. Production environment-variable and secret-file values are likewise never printed.

---

# Security and Sharing Notes

Private/runtime files must not be committed or shared:

- `.env`
- `.owner_inbox.json`
- `.git/`
- `logs/`
- `instance/` runtime contents
- `_backups/`
- API tokens, Render tokens, GitHub tokens, Gmail App Passwords, `SECRET_KEY`, `DATABASE_URL`, or `OWNER_INBOX_TOKEN`

The private owner inbox is intentionally absent from public navigation, footer, sitemap, and visitor-facing pages. Unauthenticated direct access returns 404.

The desktop inbox launcher uses a locally stored bearer token only to request a short-lived signed browser access ticket. The bearer token itself is not placed in the browser URL.
