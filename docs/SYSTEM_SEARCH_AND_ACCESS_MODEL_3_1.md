# KEY CASTRO — Systems Search + Access Model Contract (3.1.0)

## Purpose

Version 3.1.0 prepares the Systems library for growth without turning it into a marketplace or adding premature search infrastructure. The catalog remains fully server-rendered and indexable. JavaScript only filters the cards already present in the page.

## Search architecture

Source of truth: `app/system_templates.py`.

Each `SystemTemplate` exposes `search_text`, built from intentional business-facing metadata:

- name
- category
- short description
- card audience
- business problem
- target users
- optional `search_terms` aliases

Do not add system-specific conditions to `main.js`. A future published system should become searchable by adding correct metadata to the registry.

Search intentionally does **not** require a database, external search service, or a new Flask results route. That can be reconsidered only when the library size or analytics justify it.

## Progressive enhancement

Without JavaScript, the search control remains hidden and all systems remain visible in normal server HTML. With JavaScript, the control becomes visible and filters cards instantly. SEO content, system URLs, canonical metadata, sitemap behavior, and normal navigation do not depend on JavaScript.

## Search UX

- Label: **Find a system**
- Placeholder: **Search by business need...**
- Multiple words use AND-style matching against the normalized metadata text.
- Result count is announced through an `aria-live` status.
- Clear search is a text button, not an icon-only control.
- Escape clears an active query while focus remains in search.
- A no-match query becomes a useful path to **Discuss a Custom System**.

The no-match state does not pretend that a system exists. For example, a need such as CRM may correctly produce no ready-made match and invite a custom-development discussion.

## Commercial access rule

### Free standard system

The existing published version can be requested for free **in its current form**. That means its existing interface, workflow, structure, features, and functionality.

### Paid custom development

If a business needs different workflows, features, branding, permissions, database behavior, integrations, reports, deployment configuration, additional modules, or other business-specific changes, that work is a paid custom-development project.

Do not describe the free system as intentionally incomplete or inferior. Use the neutral rule: **start with the free standard system; customize it for the business when needed.**

## Where to communicate the rule

- Systems index: one concise explanation.
- System card: only the existing `FREE STANDARD SYSTEM` label and actions.
- System detail: explicit standard-scope vs paid-customization explanation.
- Contact: context-aware wording for Free Template Access vs Custom System / Customization.

Do not repeat a long paragraph in multiple sections.

## Security and attribution

Search does not change the inquiry trust boundary. System titles and source information are still resolved server-side from trusted registry metadata. Never trust an arbitrary browser-submitted source title. Owner Inbox routes remain private and absent from public navigation/search/sitemap.
