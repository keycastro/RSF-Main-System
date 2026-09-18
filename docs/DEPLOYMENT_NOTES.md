# Key Castro Website — Deployment Notes

Version 2.2.0 is designed so the same Flask website can run locally on Windows now and later be deployed publicly.

## Local vs production

Local Windows tools are separate from the website itself:

- `KEY_CASTRO_LAUNCHER.ps1`
- Desktop shortcut
- `START_KEY_CASTRO_WEBSITE.bat`
- `STOP_KEY_CASTRO_WEBSITE.bat`

The deployable web entry point is:

```text
wsgi:app
```

## Required production environment

Set these values in the hosting provider's environment settings. Do not commit a production `.env` file.

```text
APP_ENV=production
SECRET_KEY=<strong-random-secret>
PUBLIC_BASE_URL=https://your-domain.com
TRUSTED_HOSTS=your-domain.com,www.your-domain.com
CONTACT_EMAIL=<verified-business-email>
CONTACT_DELIVERY_MODE=smtp
SMTP_HOST=<mail-server>
SMTP_PORT=465
SMTP_USERNAME=<mail-user-if-required>
SMTP_PASSWORD=<mail-password-if-required>
SMTP_FROM_EMAIL=<verified-sender>
SMTP_USE_SSL=1
SMTP_USE_TLS=0
```

The production app intentionally refuses to start if the main public URL, trusted hosts, contact email, or required mail-delivery settings are missing. This prevents launching a public site with a broken contact path.

## Before going live

1. Add only verified public email and social/profile URLs.
2. Configure SMTP and test a real contact-form message.
3. Use HTTPS.
4. Set the correct `PUBLIC_BASE_URL` and `TRUSTED_HOSTS`.
5. Keep secrets only in environment variables.
6. Test desktop, tablet, and mobile layouts.
7. Confirm the Nexus case-study status wording is still accurate.
8. Confirm all project screenshots contain no private client information.
9. Run the automated tests.
10. Make a stable backup before deployment.

## Security basics already included

- HttpOnly and SameSite session cookie settings
- Secure session cookie in production
- CSRF token on the contact form
- Honeypot spam field
- Input length checks and validation
- Security response headers
- Local-only binding for the Windows development launcher
- `robots.txt` blocks indexing outside Production
- Production environment validation

## Contact form

Local development stores successful test messages in:

```text
instance/contact_messages.jsonl
```

Production uses SMTP and does not depend on that local file.
