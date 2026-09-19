# KEY CASTRO Website — Human Clarity & Older-User UX 3.8.0

## Purpose

Version 3.8.0 is a focused simplification of the existing Flask website. It keeps the established ivory/navy/sage brand, architecture, routes, security, contact flow, three published systems, and commercial rules while making the public experience easier for first-time, non-technical, older, and basic-English visitors.

## Concrete audit findings

- The old **Services** label did not explain what the page was for.
- The public site exposed too many internal business terms too early: *workflow*, *Full Handover*, *managed maintenance*, *custom build*, *roles*, and related technical wording.
- System-detail pages mixed explanation of the system with repeated post-build management choices, creating decision fatigue.
- Home used abstract process words such as **Choose / Adapt / Deliver** instead of everyday actions.
- Several system descriptions and features were technically correct but required software knowledge.
- Repeated category micro-labels and repeated links added visual noise without helping a three-system catalog.
- Some supporting text was visually too small for an older-user-friendly experience.

## Final public mental model

A visitor should be able to explain the website like this:

1. Key Castro builds simple systems for real estate businesses.
2. There are existing systems I can choose from.
3. If none fit, a new system can be built for my business.
4. After it is built, I can manage it or Key Castro can manage it.
5. I send a message to start.

## Information architecture

Primary navigation:

- Home
- Systems
- How It Works
- About
- Contact

The canonical `/services` route is preserved for SEO and backward compatibility; only its public label changed to **How It Works**.

Each public page now has one main job:

- **Home:** explain what Key Castro does.
- **Systems:** show the three systems already built.
- **System detail:** explain one system in plain language.
- **How It Works:** explain the business process and the two post-build choices.
- **About:** explain how Key Castro works.
- **Contact:** collect one simple inquiry.

## Public wording changes

- **Services** → **How It Works**
- **Full Handover** is no longer a primary public-facing label. The plain-language choice is **You Manage It**.
- **Managed by KEY CASTRO / managed maintenance** is no longer the primary public-facing label. The plain-language choice is **I Manage It**.
- The exact internal/business terms remain in the code and documentation where needed for trusted inquiry logic and historical compatibility.
- System pages use human actions such as **Your team signs in**, **Add or update a property**, and **Search for the property you need**.

## Commercial rules preserved

System creation still has two paths:

1. Customize an existing KEY CASTRO system.
2. Build a new custom system.

After build, there are still exactly two management options:

1. Full Handover — **I build it. You manage it.**
2. Managed by KEY CASTRO — **I build it. I manage it.**

Managed-maintenance pricing remains **$49/month or $490/year**. Build/customization pricing remains separate.

## Visual and accessibility refinement

- Larger everyday body/supporting text.
- Minimum 48px primary button height.
- Clearer line-height and reading width.
- Fewer visible micro-labels.
- Fewer competing CTAs.
- Three-system grid retained and balanced.
- Screenshots remain compact supporting evidence.
- Mobile layouts remain single-column where appropriate.
- Existing contrast, keyboard focus, reduced-motion support, semantic structure, and form labels remain protected.

## Security and engineering boundaries

Unchanged:

- Flask architecture
- contact form and CSRF protection
- trusted server-side inquiry source/price context
- database-backed private owner Inbox
- private authentication boundary
- canonical URLs and redirects
- sitemap and robots configuration
- GitHub + Render release workflow

No secrets belong in release ZIPs or Git commits.

## Release acceptance

The release is not considered live until the controlled updater/deployer reports:

`LIVE DEPLOYMENT VERIFIED SUCCESSFULLY`

and production health reports version `3.8.0` with all three published systems present.
