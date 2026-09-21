# REALTY SYSTEMS FOUNDRY WEBSITE 3.9.1 — RELEASE AUDIT

## Scope
- Local project folder changes from **KEY_CASTRO_WEBSITE** to **REALTY_SYSTEMS_FOUNDRY**.
- Main desktop shortcut becomes **REALTY SYSTEMS FOUNDRY**.
- Private inbox desktop shortcut becomes **RSF INBOX**.
- Local launcher/setup helper filenames are aligned to the Realty Systems Foundry identity.
- Desktop shortcut icon uses the already-approved RSF brand mark.

## Migration safety
- Existing local folder is renamed in place so `.git`, `.env`, `.owner_inbox.json`, `.venv`, and other local state are preserved.
- If both old and new local folders already exist, automatic migration stops safely instead of overwriting either one.
- Old desktop shortcuts are removed only as part of successful shortcut recreation.

## Public website and business rules preserved
- Public company brand remains **Realty Systems Foundry**.
- **Key Castro** remains **Founder, Realty Systems Foundry**.
- Home headline remains **“We Build Custom Systems for Real Estate Businesses.”**
- Existing design, routes, cards, typography, three-system catalog, and business logic remain unchanged.
- Existing ready-built system price remains **$199 one-time**.
- Self-managed technical care remains **$0/month management fee**.
- Optional managed care remains **$39/month or $390/year**.
- Minor Upgrade remains **$79**; Major Upgrade remains **$149**; New System / Large Expansion remains **Price by Agreement**.

## Infrastructure preserved
- GitHub repository names are unchanged.
- Render service identifiers are unchanged.
- Current live URL remains `https://keycastro.onrender.com` until the preferred custom domain is connected.

## Release security
- Safe release ZIP excludes `.env`, `.owner_inbox.json`, `.git`, `.venv`, backups, caches, logs, and database files.
- Exact sensitive values from the authoritative local configuration were checked and are not present in the release archive.
- Production success requires the complete test suite and final live verification for version **3.9.1**.
