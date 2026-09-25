## v1.8.3 naming

- Current website remains `https://realtysystemsfoundry.onrender.com/` because `https://rsf.onrender.com/` is unavailable.
- Partner Workspace: `https://partner-rsf.onrender.com/`.
- Future domains: `https://rsf.com/` and `https://partner.rsf.com/`.

# RSF Main System — v1.5.2

This is the single RSF application: the public Realty Systems Foundry website and the private Founder/Partner operating workspace share one backend and one database.

## End-to-end workflow

Visitor → Website Inquiry → shared Unclaimed Client Inbox → one Partner atomically claims → inquiry disappears from every other Partner → claimed Partner + Founder see the full client conversation → official RSF email → Lead → Follow-up → Demo → Proposal → Sale → Commission.

## v1.3.0 operational hardening

- Automatic background import of replies from the official RSF mailbox after IMAP is configured.
- Real-time in-app Client Inbox badges/toasts for new opportunities, client replies, reassignment, bounce events, and overdue first responses.
- First-response target and Founder/Partner overdue visibility for claimed clients.
- Client email attachments are sent/received inside RSF and stored privately outside public/static files.
- Outbound client messages record Sent/Failed and basic bounced-email state.
- Exact existing-client ownership stays protected; possible multi-signal duplicates are surfaced to Founder for review.
- Reassignment moves the Lead, open Follow-ups, and Client Conversation together while preserving history.
- Partner deactivation is blocked while active clients/leads/open follow-ups remain.
- Automatic protected data backups with configurable BACKUP_DIR; the destination can be an off-site/cloud-synced mounted folder.
- Deployment-ready Dockerfile/Procfile included. SQLite remains intentional for the current small RSF operation using one server instance; PostgreSQL is deferred until real multi-instance scale requires it.

## Official RSF email

Partners and Founder reply inside RSF, but clients see one company identity. Configure `RSF_EMAIL_ADDRESS`, `SMTP_*`, and `IMAP_*` in `.env`. Partner personal emails are never used for client mail.

## Routes

- Public website: `https://realtysystemsfoundry.onrender.com/`
- Private workspace: `https://partner-rsf.onrender.com/`

## Data safety

The Windows updater preserves `.env`, the SQLite database, internal message uploads, profile pictures, protected client attachments, accounts, passwords, Leads, Follow-ups, Sales, Commissions, internal Messages, and existing privacy/security rules. Schema migration 10 upgrades the unified workflow without wiping existing business data.

---


**Version:** 1.1.15
**Company:** Realty Systems Foundry (RSF)

RSF Partner System is the internal workspace for partners, leads, follow-ups, sales, commissions, resources, private messages, voice calls, and activity history.

## Install / update

The app uses one folder only:

`Documents\RSF Partner System`

Setup keeps the existing database, login accounts, passwords, and local settings. It updates the app, verifies access rules, and recreates the online Desktop shortcuts for the deployed website and private workspace.

## Access rules

- Founder/Admin can manage the full system and can change their own password from Profile.
- Partners can see only their own leads, follow-ups, sales, commissions, and assigned rate.
- The complete commission ladder stays Founder-only.
- Only Founder/Admin can set or reset a partner password. Partners cannot change their own password.
- Commission history keeps the rate used when each commission was created.





## v1.1.13 Emerald + Champagne identity

- Adopted the approved emerald + champagne RSF mark as the official desktop, favicon, sidebar, mobile header, and login identity.
- Reworked the visual system around deep emerald, warm ivory, and restrained champagne accents while keeping working surfaces practical and readable.
- Updated navigation, dashboards, cards, tables, forms, buttons, status badges, Messages, calls, profile, settings, and responsive views to feel like one RSF product.
- Preserved the full-workspace Messages layout, private attachments, one-way Founder read status, voice calls, partner isolation, accounts, passwords, database records, and installer/update behavior.

## v1.1.12 full-workspace Messages

- Messages now owns the available application workspace instead of floating in a centered card.
- Founder view keeps a compact conversation rail beside the active thread.
- Partner view uses the full main content area with the conversation header, thread, and composer as one continuous workspace.
- Mobile uses a dedicated full-screen conversation layout.
- Existing private messaging, protected attachments, one-way Founder read status, and simple voice calling are unchanged.

## v1.1.11 full-system simplification

- Simplified both Founder/Admin and Partner views across dashboards, navigation, leads, follow-ups, sales, commissions, partners, resources, settings, profile, activity, and Messages.
- Removed repeated page explanations and duplicate navigation actions. Partner navigation now keeps **Add Lead** as a clear page action instead of repeating it in the sidebar.
- Shortened labels, confirmations, empty states, helper text, and success/error messages while keeping important business rules clear.
- Reduced page padding, card height, table spacing, and empty-state height for a more compact desktop and mobile experience.
- Lead details no longer repeat the company and contact name inside the details panel.
- Long Resource content now uses simple progressive disclosure so the Resources page stays compact without hiding the full text.
- Verification: 120 automated tests passed, Python and JavaScript syntax checks passed, and a copy of the uploaded operational database passed Founder/Partner page and privacy smoke checks.
- No business rules, permissions, privacy boundaries, commission logic, lead ownership logic, existing Messages, attachments, voice calls, database records, or login accounts were changed.

## v1.1.9 compact Messages redesign

- Messages now use a compact, familiar private-chat layout inspired by current messaging-app patterns without copying Messenger branding.
- Founder sees a simple Partner conversation list; Partners still see only their private Founder conversation.
- Composer is one compact row: **Attach + message + Send**. Enter sends; Shift+Enter adds a new line.
- Windows clipboard screenshots can be pasted directly into the message box with **Ctrl+V**, previewed, removed, and sent.
- Photos and common work files can be attached. Images appear as compact protected previews; documents show a simple download action.
- Attachments are stored outside public static files under random names and every file request is authorized against the private Founder ↔ Partner conversation.
- Founder-only read status is asymmetric by design: the Founder can see **Seen** when the Partner reads the latest Founder message. Partner responses never receive the Founder read state.
- Existing simple voice calling stays in the conversation header with one Call action.
- Existing accounts, messages, database records, business rules, commission privacy, lead privacy, and Founder-only Partner password control are preserved.


## v1.1.8 voice-call simplification

- Calling stays inside each private Founder ↔ Partner conversation.
- One clear **Call** button starts a voice call.
- Incoming calls appear over any RSF page with only **Answer** and **Decline**.
- Active calls show only the person, call time, **Mute**, and **End Call**.
- Video/camera controls are not shown.
- Human call states are used: Calling, Incoming call, Connecting, In call, Call ended, Call declined, Missed call, and Call could not connect.
- Short call events appear naturally in the conversation instead of a separate call-history area.
- Server-side rules still allow only Founder ↔ one Partner. Partners cannot access another Partner's calls, signaling, messages, or history.
- Only one Founder voice call can be open at a time, preventing overlapping calls and double-start confusion.
- Stale ringing and abandoned browser call sessions are cleaned up automatically.
- Microphone and connection errors use simple English.
- Existing messages, accounts, business records, and RSF business rules are preserved.

## v1.1.7 private communication

- Added **Messages** for private Founder ↔ Partner conversations.
- Founder/Admin can open each partner conversation from one Messages page.
- A Partner can open only their own conversation with the Founder.
- There is no Partner-to-Partner messaging, partner directory, group chat, or social feed.
- New-message counts appear in the Messages navigation item.
- Added browser-based **voice calling** with Answer, Decline, and End Call controls.
- Voice is not recorded by RSF. Call signaling is private to the conversation and temporary signaling data is cleared when the call ends.
- Video is not enabled. Camera access stays blocked.
- Voice calling uses WebRTC and requires localhost or HTTPS. Some restrictive remote networks may require a TURN service later for reliable calls.
- Existing business rules, data isolation, commission privacy, passwords, and workflows remain unchanged.

## v1.1.6 simplification pass

- Simplified Founder and Partner navigation.
- Removed the forced password-change flow. Existing passwords stay unchanged during normal updates.
- Rewrote page titles, labels, buttons, help text, alerts, empty states, and error messages in plain English.
- Removed repeated headings and unnecessary explanations.
- Reduced visual spacing and card height for a more compact interface.
- Kept all existing business rules, privacy controls, login accounts, commission rules, lead ownership rules, and workflows unchanged.

The clean release ZIP does not include `.env`, the operational database, logs, virtual environments, caches, backups, `.git`, or other private local state.


## v1.1.16 Messages media viewer
Image attachments now open inside the RSF Messages workspace in a private, responsive in-app viewer rather than a new browser tab. Existing authenticated attachment routes and partner isolation are preserved.

## v1.1.17 Messages image viewer root-cause fix

- Repaired the malformed v1.1.16 viewer CSS that had been appended with literal escaped newlines and therefore was not being parsed as CSS.
- The reusable viewer is now promoted to `document.body` at runtime so it cannot be trapped inside the Messages layout or a local stacking context.
- The viewer is a true fixed, viewport-sized overlay with controlled image sizing, scroll lock, focus return, keyboard navigation, focus trapping, protected downloads, and responsive mobile behavior.
- Existing protected attachment routes and Founder/Partner access checks remain unchanged.

## v1.1.18 Messages image inspection

- Added native in-viewer Zoom In, Zoom Out, Fit/Reset, and a user-friendly zoom indicator.
- Added smooth click-drag / touch pan with bounded movement while zoomed.
- Added wheel/trackpad zoom over the image viewer, plus keyboard `+`, `-`, and `0` shortcuts.
- Added Pointer Events pinch-to-zoom support for touch devices and double-click zoom/reset.
- Previous/Next resets zoom and pan to Fit for the newly selected image.
- The viewer continues to use the original protected attachment route; no public/static attachment URL was introduced.
- Exact chat scroll position, background scroll lock, focus return, Download, ESC, Previous/Next, and the fixed modal layout remain preserved.



## v1.1.20 installer reliability fix
Setup no longer scans and terminates Python processes merely because their command line contains the RSF install folder. It verifies the running RSF HTTP service first and terminates only the PID actually listening on the configured RSF port. This prevents setup from killing its own parent process when launched with the installed virtual environment.

## v1.1.21 — Organized Messages image viewer controls

The image viewer keeps the same protected fixed-overlay zoom/pan behavior while reorganizing the toolbar into clear metadata, zoom, and primary-action groups. Desktop controls are visually separated; mobile uses a compact two-row header with the filename/close action above the centered zoom controls and keeps Download reachable without crowding the zoom group. No attachment-security, database, role, call, or message business logic changed.


## v1.1.22 — Cleaner dashboard and currency formatting
- Replaced displayed `USD` labels with currency symbols (for USD: `$`).
- Money values now show `$0.00` only when the value is truly zero.
- Dashboard/summary cards show `—` when there is no data yet.
- Count metrics keep real numbers when data exists and use `—` for unavailable states.


## v1.1.23 — Dashboard organization cleanup
- Added clearer dashboard hierarchy for both Founder and Partner views.
- Grouped top metrics, pipeline/commission summaries, and work queues into distinct sections.
- Added compact section labels, descriptions, and consistent spacing without changing any business logic.
- Preserved v1.1.22 money/count formatting, Messages, attachment security, privacy isolation, calls, and installer behavior.


## v1.1.25 — Founder profile picture verification fix
- Fixed the Partner Messages Founder avatar markup so the installed verifier checks the real rendered profile picture correctly.
- Corrected the Founder Profile card to use the existing styled profile-hero structure.
- No account, database, privacy, messaging, calling, or attachment-security logic changed.


## v1.1.26 — Per-user profile pictures
- Founder and every Partner can upload, replace, or remove their own profile picture from Profile.
- Custom images are stored privately under the runtime instance folder and served only through an authenticated authorization-checked route.
- JPG, PNG, and WEBP are validated by file signature and limited to 8 MB.
- Each user's avatar follows them through the sidebar, Messages, conversation headers, and voice-call UI.
- Existing Founder portrait remains the Founder fallback when no custom picture is uploaded.
- Installer preservation/rollback now includes private profile-picture files.


## v1.1.27 — App-wide organization pass
- Grouped the sidebar into clear Workspace, Operations/Sales Workflow, Administration, and Account sections.
- Standardized major page headers with concise context labels and descriptions.
- Reorganized Profile into a dedicated account workspace with a two-column identity/details area and separate Founder security section.
- Refined list/filter/table spacing without changing routes, permissions, data, or business logic.


## v1.1.28 — Audible call ringtone and ringback
- Added an outgoing ringback tone while the caller is waiting for the other person to answer.
- Added a distinct incoming ringtone while a Founder or Partner is receiving a call.
- Call tones stop immediately on answer, decline, cancel, connection, end, failure, missed call, tab handoff, or page exit.
- Uses native Web Audio only; no public audio assets or external service were added.
- Existing private Founder↔Partner WebRTC calling, permissions, call-state controls, and message privacy remain unchanged.

## v1.4.0 live-site recovery
The one unified Documents folder now also contains the restored Git metadata/remotes of the original REALTY_SYSTEMS_FOUNDRY website project. The live Render website remains https://realtysystemsfoundry.onrender.com/. The website Desktop shortcut opens that live site. Use DEPLOY_RSF_LIVE.bat only after the persistent-storage preflight passes.


## v1.5.1 ONLINE

The canonical local source folder is `Documents\RSF Main System`. The two desktop launchers open the live Render deployment directly: the public website at `https://realtysystemsfoundry.onrender.com/` and the private Founder/Partner workspace at `https://partner-rsf.onrender.com/`. Production relational data uses Render PostgreSQL; raw local `.env`, SQLite DB, uploads, logs, and backups are excluded from Git deployment.
