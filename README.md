# RSF Main System — v1.10.0

## v1.10.0 Founder + Partner Workspace simplification

This release simplifies the private RSF Workspace without changing the public website or core business rules. It reduces navigation clutter, assigns canonical homes to repeated information/actions, refocuses both dashboards on priority work, separates Partner details from credentials, and preserves the verified Founder-controlled password vault.

## v1.9.3 Account & Security UX redesign

- Redesigns **Settings → Account & Security** into a compact account-control dashboard with a single grouped Founder card and compact Partner rows.
- Keeps current passwords securely hashed and never pretends an existing plaintext password can be recovered.
- Founder New Password and Confirm New Password both have Show/Hide controls; after a successful change the exact new current Founder password is shown once with Show/Hide and Copy Password.
- Partner password controls expand only when requested; successful Partner changes show the exact new password once with Show/Hide and Copy Password.
- Preserves Founder-only authorization, CSRF, exact manual passwords, session invalidation, old-password rejection, Partner self-change blocking, and permanent Partner deletion safeguards.

## v1.9.2 Account & Security

- Adds a centralized Founder-only **Settings → Account & Security** workspace for Founder password control and all current Partner account/password controls.
- Founder password changes use the exact entered password, invalidate older Founder sessions, and keep only the current browser session signed in.
- Partner password changes use the exact entered password, invalidate existing Partner sessions, reject the old password, and show the new plaintext only once with a Copy Password action.
- Partner permanent deletion remains Founder-only, CSRF-protected, explicitly confirmed, and preserves historical business records.
- Removes password controls from Profile and Partner detail pages so credential management is not scattered around the workspace.

## v1.9.1 Founder Partner account-management verification patch

- Official people titles are **Founder** and **Partner** only.
- Removed the last setup-console `Founder/Admin` wording.
- Installed-system verification now explicitly reports Founder-only create/view/edit/password/delete checks, permanent-delete safety, privacy, CSRF, sessions, trusted hosts, and security headers.
- No database wipe, business-workflow change, commission change, or production-data reset is part of this patch.

## v1.8.7 Maximum audit hardening

- Hardened the existing-lead inquiry claim path with an atomic row-count check and rollback so a concurrent claim cannot continue after losing the queue race.
- Hardened untrusted Host handling so rejected Host headers return a clean HTTP 400 instead of entering the normal templated error path.
- `https://partner-rsf.onrender.com/` includes real `public/index.html` and `public/404.html` redirect entries to the existing RSF `/app/` Workspace.
- The clean FINAL release excludes `.env`, runtime databases/backups/uploads, logs, caches, and repository metadata. Existing installed private data is preserved by the installer and is never replaced by release contents.
- No account, password, client-data, commission-rule, or core business-flow reset is part of this release.

# RSF Main System — v1.9.3

Unified Realty Systems Foundry public website + private Founder/Partner workspace.

## Live URLs
- Website: https://realtysystemsfoundry.onrender.com/
- Partner Workspace: https://partner-rsf.onrender.com/

## Locked domain structure

### Now — free on Render
- Website: https://realtysystemsfoundry.onrender.com/
- Partner Workspace: https://partner-rsf.onrender.com/

### Later — own domain
- Website: https://rsf.com/
- Partner Workspace: https://partner.rsf.com/

## Clean project layout
- `app/` — Flask application, templates, static UI, business logic
- `scripts/` — Python maintenance, verification, publishing and backup tools
- `installers/` — Windows setup and online launchers
- `deployment/` — deployment commands and migration payloads
- `docs/` — current documentation plus archived historical notes/tools
- `assets/` — desktop/application icons
- `instance/` — protected local database/uploads/runtime data (preserved, not shipped in clean release)
- `runtime/logs/` — local launcher logs

Production-critical root files remain at the root intentionally: `wsgi.py`, `run.py`, `config.py`, `bootstrap.py`, requirements files, `Dockerfile`, `Procfile`, `.env.example`, `PROJECT_STATE.json`, and `VERSION.txt`.

## Data safety
The installer preserves `.env`, the local database, accounts, password hashes, uploads, profile pictures, client attachments, `.git`, and `.venv`. It reorganizes only known RSF project files and does not delete unknown user files.

## Setup / update
Use `installers\SETUP_RSF_MAIN_SYSTEM.bat`, or the one-CMD command supplied with the release. The installer recreates two online Desktop shortcuts: the public website and the private Partner Workspace. Normal use does not start localhost or require a local Python server.

## Deployment
Use `deployment\PUBLISH_RSF_ONLINE.bat` only when you intentionally want to publish the verified source.

Historical release notes and legacy tooling are retained under `docs/archive/`.
