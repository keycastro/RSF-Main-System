# DELIVERY REPORT — REALTY SYSTEMS FOUNDRY 3.9.1

## Approved change
Version **3.9.1** rebrands the local Windows workspace so it matches the already-approved Realty Systems Foundry public identity.

- Local project folder: `C:\Users\Admin\Documents\REALTY_SYSTEMS_FOUNDRY`
- Main desktop shortcut: **REALTY SYSTEMS FOUNDRY**
- Private inbox shortcut: **RSF INBOX**
- Local launcher/setup helper filenames now use the Realty Systems Foundry identity.
- The desktop shortcuts use the existing approved **RSF** brand mark.

## Safe migration
The installer detects the former `Documents\KEY_CASTRO_WEBSITE` folder and renames it **in place** when the new folder does not already exist. This preserves the existing `.git`, `.env`, `.owner_inbox.json`, `.venv`, logs, and other local/private state. If both old and new folders exist, migration stops instead of overwriting either folder.

After the full website tests pass, the installer removes the former `KEY CASTRO` / `Key Inbox` desktop shortcuts and creates the new shortcuts.

## Public website preserved
This release does **not** redesign or reposition the public website. The approved Realty Systems Foundry v3.9.0 brand/content remains intact, including the three published systems and current visual identity.

## Pricing preserved
- Existing ready-built system: **$199 one-time**
- Self-managed: **$0/month management fee**
- Optional managed care: **$39/month or $390/year**
- Minor Upgrade: **$79**
- Major Upgrade: **$149**
- New System / Large Expansion: **Price by Agreement**

## Infrastructure intentionally preserved
The current GitHub repository names, Render service identifiers, and live Render URL remain unchanged. The preferred future public domain remains **realtysystemsfoundry.com** until its DNS/Render connection is completed.

## Release validation
The release package contains no `.env`, private owner token file, databases, logs, `.git`, `.venv`, backups, or cache files. The one-run deployment workflow preserves local private configuration, runs the complete automated test suite, stages only approved files, pushes both Git repositories, triggers Render, and verifies the live **3.9.1** site before reporting success.
