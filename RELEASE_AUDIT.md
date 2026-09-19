# KEY CASTRO WEBSITE 3.6.0 — RELEASE AUDIT

- Existing premium visual design preserved.
- Business model updated to Customize Existing System / Custom Build, then Full Handover or Managed by KEY CASTRO.
- Managed maintenance pricing remains $49/month or $490/year; build/customization pricing is separate.
- Student Housing Matching and Placement System added as an independent portfolio system.
- Student Housing screenshots use synthetic demo data.
- Public pages contain no old monthly/yearly software-access wording.
- Legacy inquiry URLs remain backward compatible but normalize to current managed-service terminology.
- Private owner Inbox boundary, CSRF, trusted server-side inquiry context, SEO, sitemap, and redirects retained.
- Release excludes `.env`, `.owner_inbox.json`, `.git`, runtime logs, caches, bytecode, backups, and private runtime data.
- Automated regression suite: 29/29 passing before release staging; staging suite rerun separately during packaging.
