# KEY CASTRO — Systems Search Contract (3.1.0, commercial wording updated by 3.2.0)

## Search architecture

The Systems search remains a compact progressive enhancement over the server-rendered catalog. Search text comes from `app/system_templates.py` metadata: name, category, short description, audience, business problem, target users, and optional search terms. Do not add system-specific conditions to JavaScript.

Without JavaScript, all published systems remain visible and usable. With JavaScript, the search filters cards instantly, supports keyboard use, clear/reset behavior, visible focus, and an aria-live result status.

No-match remains a custom-development opportunity: **No matching system yet -> Discuss a Custom System**.

## Commercial model — authoritative from 3.2.0

The previous free-standard-system model is retired. Published systems now use:

- **Managed System Subscription** for ongoing access to an existing system.
- **Paid Customization** for separately scoped and priced business-specific development. The normal subscription continues while the managed system remains in use.

See `docs/SUBSCRIPTION_AND_CUSTOMIZATION_MODEL_3_2.md`.
