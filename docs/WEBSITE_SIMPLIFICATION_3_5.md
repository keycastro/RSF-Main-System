> **HISTORICAL NOTE (3.6.0):** Commercial wording in this document reflects an older release and is superseded by `docs/BUSINESS_MODEL_AND_MANAGED_MAINTENANCE_3_6.md`. Do not restore the old subscription-access model.

# KEY CASTRO — Website Simplification 3.5.0

## Goal

Make the public website easier to understand for a first-time visitor, including visitors who do not use technical English every day.

The rule for public content is:

**Short. Simple. Clear. No unnecessary repetition.**

## What changed

### Home

- One clear message: simple systems for real estate teams.
- Two obvious actions: **View Systems** and **Contact Me**.
- Removed the extra orientation panel and repeated business-model explanation.
- Pricing is no longer repeated on Home.

### Systems

- One short page introduction.
- Search stays available, but the search area is smaller and simpler.
- System cards show purpose, best-fit audience, preview, and one **View System** button.
- Pricing is no longer repeated on the catalog; pricing lives on each system detail page.

### System detail pages

- Shorter descriptions and fewer bullets.
- One clear path: understand the system, view screens, then choose a plan.
- Pricing remains authoritative here: $49/month or $490/year, saving $98/year on yearly access.
- Technical build details were removed from the main public decision path.
- Custom changes remain available with one clear **Request Customization** action.

### Services

- Reduced to two choices only:
  1. Use a ready-made system.
  2. Request custom work.
- Removed the separate payment-explanation section and kept the necessary subscription/custom-work distinction in one short note.

### About

- Shorter introduction.
- Three simple steps: Understand, Build, Test and deliver.
- Removed separate Skills and Experience choices from the normal visitor journey.

### Skills and Experience URLs

- `/skills` and `/experience` now permanently redirect to `/about`.
- They are removed from the sitemap and footer navigation.
- This avoids duplicate credibility pages while preserving old inbound URLs.

### Contact

- One clear heading and short next-step message.
- Shorter form labels and helper text.
- Existing secure context, CSRF, inquiry storage, trusted system title, and trusted plan resolution stay unchanged.

## What did not change

- Flask architecture
- PostgreSQL inquiry flow
- private owner Inbox
- owner authentication
- trusted pricing source
- plan anti-spoof protection
- system-title anti-spoof protection
- the two published systems remain separate
- Systems search remains metadata-driven
- existing canonical system URLs
- `/projects` remains a permanent redirect to `/system-templates`
- Render/GitHub deployment workflow

## Public navigation

The main navigation stays:

`Home · Systems · Services · About · Contact`

This is already simple and understandable, so no new primary navigation items were added.

## Content rule for future changes

Before adding public content, ask:

**Does the visitor really need this to understand the offer or decide what to do next?**

If no, do not add it.
