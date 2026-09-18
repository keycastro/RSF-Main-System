# KEY CASTRO — Template Library Architecture (2.9.0 current state)

## Purpose

The website now serves three connected roles: professional portfolio, curated free/standard real-estate system library, and client-acquisition path for paid customization/custom development.

The architecture was prepared in 2.7.0 and activated in 2.8.0 with two real systems. It remains part of the existing Flask application; no CMS, SPA framework, or separate marketplace was introduced.

## Published systems

The source-controlled registry in `app/system_templates.py` currently publishes:

- `property-operations-command-center`
- `property-inventory-hub`

Read `docs/PUBLISHED_SYSTEM_TEMPLATES.md` for exact source-grounded product claims and truth boundaries. They are separate applications and must not have their screenshots, features, workflows, or databases mixed.

## Route contract

```text
/system-templates
/system-templates/<stable-slug>
```

Published entries automatically appear in the library, public navigation, and sitemap. Draft entries remain non-public. Legacy `/projects/<published-template-slug>` paths redirect permanently to the canonical system-template detail URL; Nexus Properties is no longer a public current project and `/projects/nexus-properties` returns 404.

## Reusable metadata

`SystemTemplate` stores stable slug, name/category, descriptions, business problem, target users, workflow, features, technology, standard/free scope, customization opportunities, status, screenshots, optional real video data, project truth-boundary note, SEO metadata, and dates.

Do not create a dedicated route/template for each future system unless the generic architecture genuinely cannot represent it.

## Free-template / paid-customization conversion

Published systems are now offered through **Managed System Subscription** access. Public pricing is not shown until finalized; subscription details are discussed through Contact. Business-specific changes are separately priced **Paid Customization**.

Supported CTA patterns:

```text
/contact?template=<slug>&intent=free-access
/contact?template=<slug>&intent=customize
```

The server resolves the submitted slug against the published registry instead of trusting a visitor-supplied title.

The inquiry schema now supports backward-compatible optional context:

```text
source_type
source_slug
source_title
source_action
```

`source_action` stores a readable request type such as `System Subscription` or `Paid Customization`. Generic Contact submissions continue to work with empty source fields.

## SEO/search behavior

The architecture supports unique titles/descriptions, canonical URLs, Open Graph/Twitter metadata, descriptive media alt text, Person/WebSite structured data, and truthful SoftwareApplication + BreadcrumbList data for published systems. VideoObject is emitted only when real required video metadata exists.

The sitemap includes only public/indexable pages and published system templates. Private owner routes remain excluded. No fake reviews, ratings, clients, awards, pricing, or result claims belong in schema or copy.

## Public/private boundary

The system library must never expose Admin, Inbox, Owner Dashboard, Login, owner tokens, database credentials, inquiry data, or owner-session details. `/owner/*`, `/__owner_api/*`, and `/__owner_access/*` remain private/noindex and absent from public navigation/sitemap.

## Demo isolation rule

Any future live demo must use sample data and a separate runtime/database/secrets from the production KEY CASTRO inquiry/owner environment. Never connect a public demo to the production inquiry database or owner authentication.

The current system media are source-derived interface previews using sample/demo data. They must not be described as live client-data screenshots.

## Adding another system safely

Before changing status to `published`, confirm the actual system exists and has been inspected; the content is useful and source-grounded; the slug is stable; screenshots/video are real or accurately disclosed; standard/free scope and paid-customization boundary are clear; Contact attribution works; SEO metadata is complete; private/public separation still passes; tests pass; and production verification succeeds.

Do not create thin pages merely for search traffic. Write useful pages around actual business problems and working systems.

## 2.9.0 public naming / information architecture

The stable route contract remains `/system-templates` and `/system-templates/<stable-slug>` for SEO and backward compatibility, but the visible public navigation label is now simply **Systems**.

The former `/projects` index duplicated the same published system registry and now permanently redirects to `/system-templates`. Do not create a second catalog for the same items. One published system should have one canonical detail page and one clear browse destination.

System detail pages follow the shared hierarchy documented in `docs/UX_INFORMATION_ARCHITECTURE.md`, with technical/build details progressively disclosed rather than competing with the business explanation.
