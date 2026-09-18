# KEY CASTRO — Template Library Foundation (2.7.0)

## Why this foundation exists

The website is evolving from a portfolio into a three-part platform:

1. professional portfolio and completed case studies;
2. curated free/standard real-estate system templates and demonstrations; and
3. a client-acquisition path for paid customization and custom development.

Release 2.7.0 prepares the existing Flask application for that model **without publishing an empty template library and without changing the existing public/private architecture**.

## Current-source audit

### Already strong

- Server-rendered Flask pages are directly indexable and do not depend on a JavaScript framework.
- Public routes are stable and simple.
- The Nexus case study already demonstrates a real workflow with screenshots and a clear portfolio-status boundary.
- The Contact form already has CSRF protection, validation, a honeypot, and PostgreSQL delivery.
- The private owner inbox is already part of the same Flask codebase, authenticated through a token-to-short-lived-ticket flow, absent from public navigation, and excluded from the sitemap.
- `robots.txt`, `sitemap.xml`, canonical tags, Open Graph basics, responsive CSS, visible focus states, reduced-motion handling, and custom 404 behavior already exist.
- Project screenshots are reasonably sized and do not require a new media platform yet.

### Gaps that matter before the first template

- There was no reusable system-template content model or stable route contract.
- Publishing a future library would otherwise encourage duplicated route/template code.
- SEO metadata was page-level but not yet structured for project/template-specific titles, social metadata, breadcrumbs, or truthful structured data.
- Search Console/Bing verification had no environment-driven integration point.
- The inquiry table did not have optional source context, so future template conversions could not be attributed cleanly.
- The sitemap was hard-coded with no safe way to include only published templates.
- Error pages had no explicit noindex metadata.
- The developer handoff version had fallen behind the actual production version, showing why foundation state must be documented alongside code.

## What 2.7.0 prepares now

### 1. Reusable template registry

`app/system_templates.py` defines a source-controlled `SystemTemplate` structure containing:

- stable slug
- name / category
- short and full descriptions
- business problem
- target users
- workflow
- features
- screenshots
- video metadata and written summary/transcript field
- technology
- standard/free scope
- customization opportunities
- draft/published status
- SEO title / meta description / OG image
- publication/update dates

The registry is intentionally empty in 2.7.0.

**Draft or absent content is not public.** `/system-templates` and template-detail routes return 404 until at least one real template is deliberately marked published.

### 2. Generic future routes and templates

The stable route contract is now reserved:

```text
/system-templates
/system-templates/<stable-slug>
```

Generic server-rendered index/detail templates are ready for the first real template. Public navigation/footer links only appear when at least one published template exists.

### 3. Search foundation

The base layout now supports:

- stronger unique SEO titles
- per-page meta descriptions
- canonical URLs
- Open Graph title/description/image/image-alt
- Twitter summary-card metadata
- optional Google Search Console verification
- optional Bing Webmaster Tools verification
- truthful Person + WebSite JSON-LD
- BreadcrumbList JSON-LD on the Nexus case study
- future SoftwareApplication / VideoObject JSON-LD only for real published template content
- explicit noindex metadata on error pages

No fake rating, review, pricing, award, client, or result schema is used.

### 4. Sitemap behavior

The sitemap continues to contain only public/indexable pages. The system-template index and detail URLs are added automatically only when real published template content exists.

Private owner routes remain excluded.

### 5. Lead-source foundation

The inquiry database adds three optional, backward-compatible fields:

```text
source_type
source_slug
source_title
```

Existing generic inquiries remain valid with empty values.

A future template CTA can link to:

```text
/contact?template=<stable-slug>
```

The server resolves the slug against the published template registry. It does **not** trust arbitrary client-supplied source titles. When the template exists, the Contact page carries the source slug and stores trusted source context with the inquiry.

The owner inbox displays the source only when it exists.

## What is deliberately NOT built yet

- No fake/placeholder system templates.
- No public Template Library navigation while the registry is empty.
- No CMS or template-content database.
- No template search/filter engine.
- No download/licensing system.
- No analytics platform.
- No demo environment.
- No pricing table.
- No many-keyword SEO landing-page farm.
- No migration away from Flask/server-rendered HTML.

These should be added only when a real flagship template creates a genuine need.

## Architecture decision locked for the first template

Start source-controlled.

```text
SystemTemplate metadata (Python)
        ↓
Generic Flask index/detail routes
        ↓
Generic Jinja templates
        ↓
Real screenshots/video/transcript
        ↓
/contact?template=<slug>
        ↓
Existing inquiry database + source context
        ↓
Existing private owner inbox
```

Only consider a CMS/database for template content after source editing becomes a real operational burden.

## Demo isolation rule

A public system demo must never reuse the production website inquiry database, owner token, owner session secret, private client data, or production credentials.

Recommended future model:

```text
KEY CASTRO production portfolio
  - portfolio database / inquiry database
  - owner authentication
  - production secrets

SEPARATE public demo environment
  - sample data only
  - separate database
  - separate secret key
  - separate environment variables
  - no owner inbox blueprint/data
  - resettable demo records where practical
```

Do not clone production data into a demo. Do not expose source packages containing `.env`, `.owner_inbox.json`, credentials, tokens, or real inquiries.

## First flagship template recommendation

**Property Maintenance Management System**

Why this should be first:

- It is strongly aligned with property operations and the current niche.
- Its workflow is easy for a business owner to understand visually: report → triage → assign → update → complete → history.
- It supports a clear demonstration video and meaningful screenshots.
- It has obvious customization opportunities: roles, vendors, priorities, SLA rules, notifications, property/unit fields, approval steps, dashboards, and reporting.
- It does not duplicate the existing Nexus off-market listing case study.
- It is narrower and safer to standardize than a full rental-management platform involving payments, leases, accounting, and tenant data.

The first template should prove the full pattern before a second template is started.

## Definition of done for the first public template

A template is not ready merely because its page renders. It must have:

- working standard system/demo
- realistic sample data only
- complete metadata
- useful written explanation
- workflow
- real screenshots
- video demonstration plus written summary/transcript
- explicit standard/free scope
- explicit customization opportunities
- stable slug
- unique title / description / canonical
- accurate structured data
- sitemap inclusion
- responsive/accessibility checks
- CTA to Contact carrying source context
- source visible in private Inbox
- production verification

## Search-engine onboarding when content is ready

The code now supports verification-token meta tags through environment variables:

```text
GOOGLE_SITE_VERIFICATION
BING_SITE_VERIFICATION
```

When the owner creates those accounts:

1. verify `https://keycastro.onrender.com`;
2. submit `/sitemap.xml`;
3. monitor indexing/crawl issues;
4. monitor real search queries and page impressions;
5. improve pages from actual data rather than keyword stuffing.

## Technical debt to avoid

- Duplicating a new Jinja file and route for every template instead of using the registry/generic page.
- Changing an indexed template slug without a redirect.
- Trusting URL/form values for inquiry source titles instead of resolving server-side metadata.
- Mixing template demo databases with production inquiry data.
- Creating dozens of thin pages before one complete flagship template is proven.
- Turning Projects and System Templates into the same concept; they serve different credibility purposes.
- Introducing a CMS, SPA framework, or marketplace architecture before there is enough content to justify it.
