# Developer Handoff

This repository is the single source-code project for the Key Castro public website and private online owner inbox.

Read in order:

1. `00_FUTURE_DEVELOPER_READ_THIS_PLAN.md` *(local/private roadmap on the owner's working copy)*
2. `docs/FUTURE_TEMPLATE_LIBRARY_ROADMAP.md` *(local/private roadmap on the owner's working copy)*
3. `NEXT_DEVELOPER_READ_THIS_FIRST.md`
4. `docs/UX_INFORMATION_ARCHITECTURE.md`
5. `docs/VISUAL_PRESENTATION_3_0.md`
6. `docs/TEMPLATE_LIBRARY_FOUNDATION.md`
7. `PROJECT_STATE.json`
8. `docs/UPDATE_AND_DEPLOY_WORKFLOW.md`
9. `SECURITY_AND_SHARING_NOTES.md`

Do not split the owner inbox back into a separate project folder. Do not expose owner-only routes or secrets in public UI, GitHub, logs, screenshots, or documentation.

## Public IA contract from 2.9.0

Primary navigation is **Home · Systems · Services · About · Contact**.

`Systems` is the one public browse destination for the two published independent systems. `/projects` is a permanent legacy redirect to `/system-templates`; do not recreate a second competing systems catalog without a new, distinct information need.

`Skills` and `Experience` remain public/indexable secondary credibility pages reached through About/footer, not primary navigation.

The two published systems remain separate applications and must stay separate in claims, screenshots, workflow, and metadata. Do not publish placeholder/thin systems. Read `docs/PUBLISHED_SYSTEM_TEMPLATES.md` before changing their public positioning.


## Presentation contract from 3.0.0

Keep the premium KEY CASTRO identity, but do not return to screenshot-led pages with natural-ratio images consuming most of the viewport. Catalog and homepage previews must remain controlled and compact; system detail screenshots remain expandable through the lightbox. Preserve readable type and obvious actions while keeping vertical travel intentional. See `docs/VISUAL_PRESENTATION_3_0.md`.
