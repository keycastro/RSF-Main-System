# REALTY SYSTEMS FOUNDRY WEBSITE 3.9.0 — RELEASE AUDIT

- Public brand changed from **Key Castro** to **Realty Systems Foundry**.
- Key Castro is presented as **Founder, Realty Systems Foundry**.
- Home headline: **“We Build Custom Systems for Real Estate Businesses.”**
- Primary positioning no longer uses “simple systems.”
- Existing design language is preserved; only a small brand-name fit rule was added.
- Existing ready-built system price remains **$199 one-time**.
- Managed care remains optional at **$39/month or $390/year**.
- Self-managed technical care remains **$0/month management fee**.
- Minor Upgrade remains **$79**; Major Upgrade remains **$149**; New System / Large Expansion remains **Price by Agreement**.
- Current Render URL remains the working production host until **realtysystemsfoundry.com** is connected through DNS/Render.
- Live deployment is valid only after production verification confirms version **3.9.0**, the rebrand, preserved pricing, and preserved three-system catalog.

## Pre-deployment test correction

- The first deployment attempt stopped safely before Git push because the clarity test required the optional direct-email line even when `CONTACT_EMAIL` was intentionally blank in the test configuration.
- The test now checks that line only when `CONTACT_EMAIL` is configured, matching the existing template behavior.
- No public layout, pricing, routes, or rebrand copy were changed by this correction.
