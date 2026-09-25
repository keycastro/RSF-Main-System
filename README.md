## v1.8.7 Maximum audit hardening

- Hardened the existing-lead inquiry claim path with an atomic row-count check and rollback so a concurrent claim cannot continue after losing the queue race.
- Hardened untrusted Host handling so rejected Host headers return a clean HTTP 400 instead of entering the normal templated error path.
- `https://partner-rsf.onrender.com/` includes real `public/index.html` and `public/404.html` redirect entries to the existing RSF `/app/` Workspace.
- The clean FINAL release excludes `.env`, runtime databases/backups/uploads, logs, caches, and repository metadata. Existing installed private data is preserved by the installer and is never replaced by release contents.
- No account, password, client-data, commission-rule, or core business-flow reset is part of this release.

# RSF Main System — v1.8.7

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
