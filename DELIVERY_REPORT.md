# Delivery Report — 2.4.0

## Change

Consolidated the Key Castro website and owner inquiry inbox into one Flask project/codebase while preserving two desktop launchers.

## Public visitor experience

Unchanged: public pages remain open without login. No owner/admin/inbox/login link is added to visitor-facing navigation, footer, homepage, sitemap, projects, or case studies.

## Private owner experience

`KEY CASTRO INBOX` securely opens the deployed online inbox through a short-lived access ticket and authenticated Flask session. The inbox uses the existing contact inquiry database and supports New, Read, Replied, Archived, and Reply by Email.

## Folder result

After the migration installer verifies the live website and private inbox, the old separate `KEY_CASTRO_INBOX` folder is backed up and removed. The active project remains only `KEY_CASTRO_WEBSITE`.
