"""Verify the installed RSF system without changing passwords or business records."""
from __future__ import annotations

import os

import html
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["RSF_DISABLE_BACKGROUND"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.db import get_db
from app.auth import session_credential, hash_password
from werkzeug.security import check_password_hash


def fail(message: str) -> None:
    raise SystemExit(message)


def verify_project_layout() -> None:
    required_dirs = ("app", "scripts", "installers", "deployment", "docs", "assets", "instance", "runtime")
    missing = [name for name in required_dirs if not (ROOT / name).exists()]
    if missing:
        fail("Organized project layout is incomplete: " + ", ".join(missing))
    forbidden_root = (
        "RSF Partner System Launcher.vbs", "Realty Systems Foundry Website Launcher.vbs",
        "RSF Partner System.ico", "RSF Partner System Desktop.ico",
        "PUBLISH_RSF_ONLINE.bat", "DEPLOY_RSF_LIVE.bat",
        "SETUP_RSF_PARTNER_SYSTEM.bat", "START_RSF_PARTNER_SYSTEM.bat",
        "online_attachment_seed.enc",
    )
    clutter = [name for name in forbidden_root if (ROOT / name).exists()]
    if clutter:
        fail("Root-folder organization check failed; obsolete root files remain: " + ", ".join(clutter))



def _visible_text(markup: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup or "")).split())


def _csrf_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    if not match:
        fail("CSRF verification failed: form token was not found.")
    return html.unescape(match.group(1))


def _login_with_password(client, email: str, password: str) -> int:
    page = client.get("/app/login", follow_redirects=False)
    if page.status_code != 200:
        fail("Login verification failed: sign-in page did not render.")
    token = _csrf_from(page)
    response = client.post(
        "/app/login",
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=False,
    )
    return response.status_code


def verify_founder_partner_account_management(source_db) -> None:
    """Destructively test v1.9 account controls only on a disposable DB copy."""
    with tempfile.TemporaryDirectory(prefix="rsf-account-audit-") as td:
        test_root = Path(td)
        test_db_path = test_root / "audit.db"
        target = sqlite3.connect(test_db_path)
        try:
            source_db.backup(target)
        finally:
            target.close()

        test_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "rsf-v1.9-disposable-verifier",
            "DATABASE_URL": "",
            "DATABASE": str(test_db_path),
            "MESSAGE_UPLOAD_DIR": str(test_root / "message_uploads"),
            "PROFILE_PICTURE_DIR": str(test_root / "profile_pictures"),
            "CLIENT_ATTACHMENT_DIR": str(test_root / "client_attachments"),
            "BACKUP_DIR": str(test_root / "backups"),
            "TRUSTED_HOSTS": ["localhost", "127.0.0.1"],
            "SESSION_COOKIE_SECURE": False,
        })

        founder_email = "founder-audit@rsf.test"
        founder_password = "f"
        founder_new_password = "q"
        partner_email = "partner-audit@rsf.test"
        first_password = "1"
        second_password = "x"
        forged_email = "forged-partner@rsf.test"

        with test_app.app_context():
            db = get_db()
            founder = db.execute("SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            if not founder:
                fail("Founder account verification failed in disposable account audit.")
            # Change only the disposable copy so the verifier can exercise real password login routes.
            db.execute(
                "UPDATE users SET email=?,password_hash=?,active=1,failed_login_count=0,locked_until=NULL WHERE id=?",
                (founder_email, hash_password(founder_password), founder["id"]),
            )
            stage = db.execute("SELECT * FROM commission_stages WHERE code='FOUNDING_1'").fetchone()
            if not stage or int(stage["rate_bp"]) != 4000:
                fail("Commission ladder check failed in disposable account audit.")
            db.commit()

        founder_client = test_app.test_client()
        if _login_with_password(founder_client, founder_email, founder_password) not in (302, 303):
            fail("Founder login check failed in disposable account audit.")

        account_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        account_html = account_page.get_data(as_text=True)
        account_visible = _visible_text(account_html)
        required = (
            "Account & Security","Founder Account","Partner Accounts","New Password","Confirm New Password",
            "Current Password","Show","Copy",
        )
        if account_page.status_code != 200 or any(item not in account_visible for item in required):
            fail("Founder Account & Security current-password workspace is incomplete.")
        source_markers = (
            "compact-password-form","data-toggle-password","compact-empty-state",
            'id="founder_current_password"',"data-vault-reveal","data-vault-copy","data-password-vault-url",
        )
        if any(marker not in account_html for marker in source_markers):
            fail("Account & Security current-password source controls are incomplete.")
        if "Hashed · not readable or recoverable" in account_visible or "Securely set" in account_visible:
            fail("Obsolete v1.9.3 current-password status is still visible.")
        founder_current_input = re.search(r'<input[^>]+id="founder_current_password"[^>]*>', account_html)
        if not founder_current_input or re.search(r'\svalue=', founder_current_input.group(0), flags=re.I):
            fail("Founder current-password field must render masked and empty; plaintext must be fetched on demand.")
        if 'name="current_password"' in account_html:
            fail("Account & Security incorrectly asks the Founder to re-enter the current password.")

        reveal = founder_client.post(
            "/app/admin/settings/account-security/reveal-password",
            data={"csrf_token": _csrf_from(account_page), "user_id": str(founder["id"])},
            follow_redirects=False,
        )
        reveal_payload = reveal.get_json(silent=True) or {}
        if reveal.status_code != 200 or not reveal_payload.get("ok") or reveal_payload.get("password") != founder_password:
            fail("Founder current-password reveal did not return the exact authenticated password.")
        if "no-store" not in reveal.headers.get("Cache-Control","") or reveal.headers.get("Pragma") != "no-cache":
            fail("Founder current-password reveal is missing no-cache response headers.")
        if founder_email not in account_html or "Founder Audit Seed" not in account_visible:
            fail("Founder identity is missing from Account & Security.")
        for forbidden in ("Founder/Admin","Founder / Admin","Employee","Staff","Deactivate","Suspend","Archive"):
            if forbidden.lower() in account_visible.lower():
                fail(f"Obsolete account terminology is visible in Account & Security: {forbidden}")
        for nag in ("too weak","stronger password","add a symbol","uppercase","lowercase","password strength","12+ characters"):
            if nag in account_visible.lower():
                fail(f"Password-strength rule remains visible in Account & Security: {nag}")

        founder_stale = test_app.test_client()
        if _login_with_password(founder_stale, founder_email, founder_password) not in (302,303):
            fail("Founder stale-session setup failed.")
        if founder_client.post(
            "/app/admin/settings/account-security/founder-password",
            data={"new_password": founder_new_password, "confirm_password": founder_new_password},
            follow_redirects=False,
        ).status_code != 400:
            fail("CSRF protection failed on Founder password change.")
        changed_founder = founder_client.post(
            "/app/admin/settings/account-security/founder-password",
            data={"csrf_token": _csrf_from(account_page), "new_password": founder_new_password, "confirm_password": founder_new_password},
            follow_redirects=False,
        )
        founder_changed_html = changed_founder.get_data(as_text=True)
        founder_reveal_markers = (
            'id="founder_current_password_once"', f'value="{founder_new_password}"',
            "This is your new current password.", "Copy it now. RSF will not store it as readable text.",
            "data-toggle-password", "data-copy-input", "Copy Password",
        )
        if changed_founder.status_code != 200 or any(marker not in founder_changed_html for marker in founder_reveal_markers):
            fail("Founder password change or one-time visibility failed from Account & Security.")
        with test_app.app_context():
            founder_after = get_db().execute("SELECT password_hash FROM users WHERE lower(email)=?", (founder_email,)).fetchone()
            if not founder_after or not check_password_hash(founder_after["password_hash"], founder_new_password) or check_password_hash(founder_after["password_hash"], founder_password):
                fail("Founder password was not replaced exactly.")
        stale_response = founder_stale.get("/app/admin/settings/account-security", follow_redirects=False)
        if stale_response.status_code not in (301,302,303,307,308) or "/app/login" not in stale_response.headers.get("Location",""):
            fail("Older Founder session was not invalidated after password change.")
        old_founder = test_app.test_client()
        if _login_with_password(old_founder, founder_email, founder_password) in (302,303):
            fail("Old Founder password still authenticates.")
        founder_after_get = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        if founder_after_get.status_code != 200:
            fail("Current Founder session was not safely rebound after password change.")
        if 'id="founder_current_password_once"' in founder_after_get.get_data(as_text=True):
            fail("Founder plaintext password persisted beyond the one-time password-change response.")
        new_founder = test_app.test_client()
        if _login_with_password(new_founder, founder_email, founder_new_password) not in (302,303):
            fail("New exact Founder password does not authenticate.")
        founder_password = founder_new_password

        founder_profile = founder_client.get("/app/profile", follow_redirects=False)
        founder_profile_html = founder_profile.get_data(as_text=True)
        if 'name="current_password"' in founder_profile_html or 'name="new_password"' in founder_profile_html:
            fail("Founder password controls are still scattered on Profile.")
        if "Account &amp; Security" not in founder_profile_html:
            fail("Founder Profile does not link to Account & Security.")

        partners_page = founder_client.get("/app/admin/partners", follow_redirects=False)
        partners_html = partners_page.get_data(as_text=True)
        if partners_page.status_code != 200 or "Partners" not in _visible_text(partners_html):
            fail("Founder Partners page check failed.")
        visible = _visible_text(partners_html)
        for forbidden in ("Founder/Admin", "Founder / Admin", "Employee/Partner", "Employee / Partner", "Employee Partner", "Partner Employee"):
            if forbidden in visible:
                fail(f"Official terminology check failed: {forbidden!r} is still user-facing.")

        new_page = founder_client.get("/app/admin/partners/new", follow_redirects=False)
        if new_page.status_code != 200:
            fail("Founder create-Partner page did not render.")
        new_html = new_page.get_data(as_text=True)
        for marker in ('name="password"', 'data-password-toggle', 'data-copy-target'):
            if marker not in new_html:
                fail("Founder password entry controls are incomplete.")
        if any(word in _visible_text(new_html).lower() for word in ("too weak", "stronger password", "add a symbol", "add an uppercase")):
            fail("Password-strength nagging is still visible on Partner creation.")

        token = _csrf_from(new_page)
        created = founder_client.post(
            "/app/admin/partners/new",
            data={
                "csrf_token": token, "full_name": "Audit Partner", "email": partner_email,
                "password": first_password, "phone": "", "notes": "Disposable verifier account",
                "commission_stage_id": str(stage["id"]),
            },
            follow_redirects=False,
        )
        created_html = created.get_data(as_text=True)
        if created.status_code != 200 or 'id="created_password"' not in created_html or f'value="{first_password}"' not in created_html:
            fail("Exact Founder-chosen Partner password was not shown after creation.")
        if "not stored as readable text" not in created_html.lower():
            fail("One-time password security notice is missing after Partner creation.")

        with test_app.app_context():
            db = get_db()
            created_row = db.execute(
                "SELECT u.*,p.id partner_id,p.commission_stage_id FROM users u JOIN partners p ON p.user_id=u.id WHERE lower(u.email)=?",
                (partner_email,),
            ).fetchone()
            if not created_row:
                fail("Partner creation did not create an account.")
            test_user_id = int(created_row["id"]); test_partner_id = int(created_row["partner_id"] )
            if created_row["password_hash"] == first_password or not check_password_hash(created_row["password_hash"], first_password):
                fail("Password security check failed: Partner password was not stored as a verifiable hash.")
            # Seed business history owned/authored by the disposable Partner. These rows must survive account deletion.
            now = "2026-09-25T21:30:00+00:00"
            lead_cur = db.execute(
                """INSERT INTO leads(owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,website,website_domain,lead_source,summary_notes,status,lost_reason,demo_at,registered_at,last_activity_at,created_by_user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'NEW','',NULL,?,?,?)""",
                (test_partner_id,"AUDIT OWN BUSINESS","audit own business","Audit Client","audit client","audit-own@rsf.test","audit-own@rsf.test","","","","","Audit","",now,now,test_user_id),
            )
            own_lead_id = int(lead_cur.lastrowid)
            own_message_id = int(db.execute(
                "INSERT INTO messages(partner_id,sender_user_id,body,created_at) VALUES (?,?,?,?)",
                (test_partner_id,test_user_id,"AUDIT PARTNER HISTORY",now),
            ).lastrowid)

            # Always create a second disposable Partner to prove cross-Partner data isolation.
            other_user_id = int(db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'partner',1,0,?,?)""",
                ("Other Audit Partner","other-audit@rsf.test",hash_password("o"),now,now),
            ).lastrowid)
            other_partner_id = int(db.execute(
                """INSERT INTO partners(user_id,full_name_snapshot,email_snapshot,commission_stage_id,phone,notes,joined_at,active)
                   VALUES (?,?,?,?,?,?,?,1)""",
                (other_user_id,"Other Audit Partner","other-audit@rsf.test",stage["id"],"","",now),
            ).lastrowid)
            other_lead_id = int(db.execute(
                """INSERT INTO leads(owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,website,website_domain,lead_source,summary_notes,status,lost_reason,demo_at,registered_at,last_activity_at,created_by_user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'NEW','',NULL,?,?,?)""",
                (other_partner_id,"OTHER PRIVATE BUSINESS","other private business","Other Client","other client","other-private@rsf.test","other-private@rsf.test","","","","","Audit","",now,now,other_user_id),
            ).lastrowid)
            db.execute(
                "INSERT INTO messages(partner_id,sender_user_id,body,created_at) VALUES (?,?,?,?)",
                (other_partner_id,other_user_id,"OTHER PARTNER PRIVATE MESSAGE",now),
            )
            db.commit()

        # Exact one-character password must authenticate.
        partner_client = test_app.test_client()
        if _login_with_password(partner_client, partner_email, first_password) not in (302, 303):
            fail("Exact arbitrary Partner password was not accepted for login.")
        if partner_client.get("/app/", follow_redirects=False).status_code != 200:
            fail("New Partner dashboard login check failed.")
        if partner_client.get("/app/admin/partners", follow_redirects=False).status_code != 403:
            fail("Founder-only Partners route is accessible to a Partner.")
        if partner_client.get("/app/admin/settings/account-security", follow_redirects=False).status_code != 403:
            fail("Founder Account & Security is accessible to a Partner.")
        if partner_client.get("/app/admin/partners/new", follow_redirects=False).status_code != 403:
            fail("Founder-only Partner creation route is accessible to a Partner.")
        if partner_client.get(f"/app/admin/partners/{test_partner_id}", follow_redirects=False).status_code != 403:
            fail("Founder-only Partner detail route is accessible to a Partner.")
        if partner_client.get(f"/app/leads/{other_lead_id}", follow_redirects=False).status_code != 404:
            fail("Partner privacy check failed: another Partner's Lead is accessible.")
        if partner_client.get(f"/app/messages/{other_partner_id}", follow_redirects=False).status_code != 404:
            fail("Partner privacy check failed: another Partner's Messages are accessible.")

        profile = partner_client.get("/app/profile", follow_redirects=False)
        profile_html = profile.get_data(as_text=True)
        if profile.status_code != 200 or "Change Password" in _visible_text(profile_html):
            fail("Partner self-service password controls are visible.")
        partner_csrf = _csrf_from(profile)
        blocked_self_change = partner_client.post(
            "/app/profile",
            data={"csrf_token": partner_csrf, "action": "password", "current_password": first_password, "new_password": "z", "confirm_password": "z"},
            follow_redirects=False,
        )
        if blocked_self_change.status_code != 403:
            fail("Partner self-service password change was not blocked at the backend.")
        for path, data in (
            ("/app/admin/settings/account-security/founder-password", {"csrf_token": partner_csrf, "new_password": "forged", "confirm_password": "forged"}),
            (f"/app/admin/partners/{test_partner_id}/reset-password", {"csrf_token": partner_csrf, "partner_password": "forged", "confirm_partner_password": "forged"}),
            (f"/app/admin/partners/{test_partner_id}/delete", {"csrf_token": partner_csrf, "confirm_delete": "1"}),
            ("/app/admin/partners/new", {"csrf_token": partner_csrf, "full_name": "Forged", "email": forged_email, "password": "p", "commission_stage_id": str(stage["id"])}),
        ):
            if partner_client.post(path, data=data, follow_redirects=False).status_code != 403:
                fail("Founder-only Partner management POST was not blocked at the backend.")
        with test_app.app_context():
            if get_db().execute("SELECT 1 FROM users WHERE lower(email)=?", (forged_email,)).fetchone():
                fail("Forged Partner creation unexpectedly created an account.")

        # Founder can view and edit the Partner.
        detail = founder_client.get(f"/app/admin/partners/{test_partner_id}", follow_redirects=False)
        detail_html = detail.get_data(as_text=True)
        detail_visible = _visible_text(detail_html)
        if detail.status_code != 200 or "Audit Partner" not in detail_visible or "Account & Security" not in detail_visible:
            fail("Founder Partner detail page or centralized security handoff failed.")
        if "Change Password" in detail_visible or "Delete Partner Permanently" in detail_visible:
            fail("Partner credential controls are still scattered on the Partner detail page.")
        edit_token = _csrf_from(detail)
        edited = founder_client.post(
            f"/app/admin/partners/{test_partner_id}",
            data={"csrf_token": edit_token, "full_name": "Audit Partner Edited", "email": partner_email,
                  "commission_stage_id": str(stage["id"]), "phone": "123", "notes": "Edited by verifier"},
            follow_redirects=False,
        )
        if edited.status_code not in (302,303):
            fail("Founder Partner edit action failed.")

        # CSRF must block a password reset before authorization/business logic.
        no_csrf = founder_client.post(
            f"/app/admin/partners/{test_partner_id}/reset-password",
            data={"partner_password": second_password, "confirm_partner_password": second_password},
            follow_redirects=False,
        )
        if no_csrf.status_code != 400:
            fail("CSRF check failed on Founder Partner password reset.")

        account_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        account_html = account_page.get_data(as_text=True)
        account_visible = _visible_text(account_html)
        partner_actions = ("View","Edit","Change Password","Delete")
        partner_source_markers = ("data-account-disclosure", f'id="partner-password-panel-{test_partner_id}"', "partner-compact-row")
        if f'id="partner-{test_partner_id}"' not in account_html or any(item not in account_visible for item in partner_actions) or any(marker not in account_html for marker in partner_source_markers):
            fail("Compact Partner account actions are incomplete in Account & Security.")
        reset_token = _csrf_from(account_page)
        changed = founder_client.post(
            f"/app/admin/partners/{test_partner_id}/reset-password",
            data={"csrf_token": reset_token, "partner_password": second_password, "confirm_partner_password": second_password},
            follow_redirects=False,
        )
        changed_html = changed.get_data(as_text=True)
        partner_reveal_markers = (
            'id="changed_partner_password"', f'value="{second_password}"', "Copy Password",
            "data-toggle-password", "data-copy-input", "new current password",
            "RSF will not store it as readable text",
        )
        if changed.status_code != 200 or any(marker not in changed_html for marker in partner_reveal_markers):
            fail("Founder exact Partner password reset/one-time visibility failed in Account & Security.")
        partner_after_get = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        if 'id="changed_partner_password"' in partner_after_get.get_data(as_text=True):
            fail("Partner plaintext password persisted beyond the one-time password-change response.")

        # Password reset invalidates existing sessions and the old password immediately.
        if partner_client.get("/app/", follow_redirects=False).status_code not in (301,302,303,307,308):
            fail("Partner session was not invalidated after password reset.")
        old_login = test_app.test_client()
        if _login_with_password(old_login, partner_email, first_password) in (302,303):
            fail("Old Partner password still authenticates after reset.")
        new_login = test_app.test_client()
        if _login_with_password(new_login, partner_email, second_password) not in (302,303):
            fail("New exact Partner password does not authenticate after reset.")

        with test_app.app_context():
            db = get_db()
            preserved_before = {table: db.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"] for table in (
                "leads","website_inquiries","client_conversations","client_messages","messages","sales","commissions"
            )}

        account_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        delete_token = _csrf_from(account_page)
        missing_confirmation = founder_client.post(
            f"/app/admin/partners/{test_partner_id}/delete",
            data={"csrf_token": delete_token},
            follow_redirects=False,
        )
        if missing_confirmation.status_code != 400:
            fail("Permanent Partner deletion did not require explicit confirmation.")
        deleted = founder_client.post(
            f"/app/admin/partners/{test_partner_id}/delete",
            data={"csrf_token": delete_token, "confirm_delete": "1"},
            follow_redirects=False,
        )
        if deleted.status_code not in (302,303) or "/app/admin/settings/account-security" not in deleted.headers.get("Location",""):
            fail("Founder permanent Partner delete action failed from Account & Security.")

        with test_app.app_context():
            db = get_db()
            if db.execute("SELECT 1 FROM users WHERE id=?", (test_user_id,)).fetchone():
                fail("Permanent Partner delete left the authentication account in users.")
            historical = db.execute("SELECT * FROM partners WHERE id=?", (test_partner_id,)).fetchone()
            if not historical or historical["user_id"] is not None or not historical["deleted_at"]:
                fail("Permanent Partner delete did not detach the historical Partner identity safely.")
            if historical["full_name_snapshot"] != "Audit Partner Edited":
                fail("Permanent Partner delete did not preserve historical Partner attribution.")
            if historical["email_snapshot"] or historical["phone"] or historical["notes"]:
                fail("Permanent Partner delete left Partner account/profile details behind.")
            own_lead = db.execute("SELECT * FROM leads WHERE id=?", (own_lead_id,)).fetchone()
            own_message = db.execute("SELECT * FROM messages WHERE id=?", (own_message_id,)).fetchone()
            if not own_lead or own_lead["owner_partner_id"] != test_partner_id or own_lead["created_by_user_id"] is not None:
                fail("Partner deletion damaged or failed to detach Lead business history safely.")
            if not own_message or own_message["partner_id"] != test_partner_id or own_message["sender_user_id"] is not None:
                fail("Partner deletion damaged or failed to detach Message history safely.")
            preserved_after = {table: db.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"] for table in preserved_before}
            if preserved_before != preserved_after:
                fail(f"Permanent Partner delete changed business-record counts: before={preserved_before}, after={preserved_after}")
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                fail("Database integrity failed after disposable Partner deletion.")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                fail("Foreign-key integrity failed after disposable Partner deletion.")

        deleted_login = test_app.test_client()
        if _login_with_password(deleted_login, partner_email, second_password) in (302,303):
            fail("Permanently deleted Partner can still authenticate.")
        if founder_client.get(f"/app/admin/partners/{test_partner_id}", follow_redirects=False).status_code != 404:
            fail("Deleted Partner still appears as a current account detail.")

        current_list = founder_client.get("/app/admin/partners", follow_redirects=False).get_data(as_text=True)
        if partner_email in current_list:
            fail("Deleted Partner still appears in the current Partners list.")

        bad_host = test_app.test_client().get("/", headers={"Host": "evil.example"}, follow_redirects=False)
        if bad_host.status_code != 400:
            fail("Trusted-host protection check failed.")
        secure_page = founder_client.get("/app/admin/partners", follow_redirects=False)
        if secure_page.headers.get("X-Content-Type-Options") != "nosniff" or secure_page.headers.get("X-Frame-Options") != "DENY":
            fail("Security-header verification failed.")
        if "no-store" not in secure_page.headers.get("Cache-Control", "") or "frame-ancestors 'none'" not in secure_page.headers.get("Content-Security-Policy", ""):
            fail("Private-page cache/CSP verification failed.")


def main() -> None:
    verify_project_layout()
    css_path = ROOT / "app" / "static" / "css" / "app.css"
    workspace_css_path = ROOT / "app" / "static" / "css" / "workspace_v18.css"
    js_path = ROOT / "app" / "static" / "js" / "app.js"
    icon_path = ROOT / "assets" / "icons" / "RSF Partner System.ico"
    brand_path = ROOT / "app" / "static" / "img" / "rsf-brand.png"
    favicon_path = ROOT / "app" / "static" / "img" / "rsf-favicon.ico"
    founder_profile_path = ROOT / "app" / "static" / "img" / "founder-profile.png"
    if not css_path.exists() or "v1.1.13 — RSF Emerald + Champagne identity" not in css_path.read_text(encoding="utf-8"):
        fail("RSF Emerald + Champagne visual update is incomplete.")
    if not icon_path.exists() or icon_path.stat().st_size < 1000:
        fail("RSF desktop icon is missing.")
    if not brand_path.exists() or brand_path.stat().st_size < 10000 or not favicon_path.exists():
        fail("RSF approved brand assets are missing.")
    if not founder_profile_path.exists() or founder_profile_path.stat().st_size < 100000:
        fail("Founder profile picture is missing or invalid.")

    css_text = css_path.read_text(encoding="utf-8")
    if workspace_css_path.exists():
        css_text += "\n" + workspace_css_path.read_text(encoding="utf-8")
    js_text = js_path.read_text(encoding="utf-8") if js_path.exists() else ""
    # Call controls must be state-specific. The explicit [hidden] rule is
    # important because the shared .button display rule would otherwise make
    # hidden call actions visible at the same time.
    if ".voice-call-actions .button[hidden]{display:none!important}" not in css_text:
        fail("Voice-call UI check failed: hidden call actions can become visible.")
    required_call_ui = (
        "showCallButtons(answerButton, declineButton)",
        "showCallButtons(cancelButton)",
        "showCallButtons(endButton)",
        "showCallButtons(muteButton, endButton)",
        "currentCall.status !== 'RINGING' || !currentCall.started_by_me",
        "currentCall.status !== 'ACTIVE' || peer?.connectionState !== 'connected'",
    )
    if any(marker not in js_text for marker in required_call_ui):
        fail("Voice-call UI check failed: call actions are not strictly state-specific.")

    required_call_audio = (
        "v1.1.28 — audible private-call feedback",
        "startCallTone('incoming')",
        "startCallTone('outgoing')",
        "syncCallTone(mode)",
        "playCallToneBurst([440, 480]",
        "playCallToneBurst([660, 880]",
        "stopCallTone();",
        "window.AudioContext || window.webkitAudioContext",
    )
    if any(marker not in js_text for marker in required_call_audio):
        fail("Voice-call audio check failed: incoming ringtone or outgoing ringback is incomplete.")

    message_template_path = ROOT / "app" / "templates" / "messages_thread.html"
    message_template = message_template_path.read_text(encoding="utf-8") if message_template_path.exists() else ""
    if "data-image-viewer" not in message_template or "data-message-image" not in message_template:
        fail("Messages image viewer check failed: in-app viewer markup is missing.")
    if 'class="message-image-link"' in message_template and 'target="_blank"' in message_template:
        fail("Messages image viewer check failed: image attachments still open in a new tab.")
    required_image_viewer = (
        "openImageViewer",
        "closeImageViewer",
        "collectViewerItems",
        "imageViewer.hidden = false",
        "data-image-viewer-img",
        "document.body.appendChild(imageViewer)",
        "image-viewer-open",
        "setViewerZoom",
        "resetViewerTransform",
        "data-image-viewer-zoom-in",
        "data-image-viewer-zoom-out",
        "data-image-viewer-fit",
        "data-image-viewer-zoom-value",
        "image-viewer-primary-actions",
        "image-viewer-control-label",
        "pointerdown",
        "event.key === '+'",
        "event.key === '0'",
    )
    if any(marker not in js_text and marker not in message_template for marker in required_image_viewer):
        fail("Messages image viewer check failed: in-app viewer behavior is incomplete.")
    required_viewer_css = (
        ".message-image-viewer{",
        "position:fixed!important",
        "inset:0!important",
        "z-index:10000!important",
        ".message-image-viewer[hidden]{display:none!important}",
        ".message-image-viewer-canvas{",
        "touch-action:none",
        "max-width:none!important",
        'grid-template-areas:"meta close" "tools tools"',
        ".image-viewer-primary-actions{",
    )
    if any(marker not in css_text for marker in required_viewer_css):
        fail("Messages image viewer check failed: fixed overlay layout is incomplete.")

    setup_path = ROOT / "installers" / "SETUP_RSF_MAIN_SYSTEM.bat"
    launcher_vbs_path = ROOT / "installers" / "launchers" / "RSF Partner System Launcher.vbs"
    launcher_py_path = ROOT / "scripts" / "LAUNCH_RSF_PARTNER_SYSTEM.py"
    installer_py_path = ROOT / "scripts" / "INSTALL_RSF_PARTNER_SYSTEM.py"
    setup_text = setup_path.read_text(encoding="utf-8", errors="replace") if setup_path.exists() else ""
    launcher_vbs_text = launcher_vbs_path.read_text(encoding="utf-8", errors="replace") if launcher_vbs_path.exists() else ""
    if not launcher_py_path.exists() or not installer_py_path.exists():
        fail("PowerShell-independent setup/launcher check failed: Python installer or launcher is missing.")
    launcher_py_text = launcher_py_path.read_text(encoding="utf-8", errors="replace")
    if "https://partner-rsf.onrender.com/" not in launcher_py_text or "127.0.0.1" in launcher_py_text or "localhost" in launcher_py_text:
        fail("Production launcher check failed: the Python launcher is not online-only.")
    if "https://partner-rsf.onrender.com/" not in launcher_vbs_text or "127.0.0.1" in launcher_vbs_text or "localhost" in launcher_vbs_text:
        fail("Production launcher check failed: the Partner shortcut is not online-only.")
    for alias_entry in (ROOT / "public" / "index.html", ROOT / "public" / "404.html"):
        if not alias_entry.is_file():
            fail(f"Partner Workspace routing entry is missing: {alias_entry.relative_to(ROOT)}")
        alias_text = alias_entry.read_text(encoding="utf-8", errors="replace")
        if "https://realtysystemsfoundry.onrender.com/app/" not in alias_text:
            fail(f"Partner Workspace routing entry does not target the RSF /app/ Workspace: {alias_entry.relative_to(ROOT)}")
    if "powershell.exe" in setup_text.lower() or "powershell.exe" in launcher_vbs_text.lower():
        fail("PowerShell-independent setup/launcher check failed: active setup or launcher still depends on PowerShell.")
    if "\\n.message-image" in css_text or "\\n\\n/* v1.1.16" in css_text:
        fail("Messages image viewer check failed: escaped newlines are corrupting viewer CSS.")

    profile_template = (ROOT / "app" / "templates" / "profile.html").read_text(encoding="utf-8", errors="replace")
    base_template = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8", errors="replace")
    routes_text = (ROOT / "app" / "routes.py").read_text(encoding="utf-8", errors="replace")
    required_profile_picture = (
        'enctype="multipart/form-data"', 'name="profile_picture"', 'value="avatar"', 'value="avatar_remove"',
        'profile-picture-manager', '@bp.get("/profile-picture/<int:user_id>")', 'PROFILE_PICTURE_MAX_BYTES',
        '_detect_profile_picture_type', 'data-call-avatar', 'currentCall.avatar_url',
    )
    combined_profile_source = profile_template + base_template + routes_text + js_text
    if any(marker not in combined_profile_source for marker in required_profile_picture):
        fail("Per-user profile-picture feature is incomplete.")

    required_organization = (
        'nav-section-label', 'Workspace', 'Sales operations', 'Founder', 'Sales workflow', 'Tools', 'Account',
        'organized-page-head', 'page-kicker', 'profile-organized-layout', 'profile-primary-grid',
        'v1.1.27 — app-wide organization pass', 'v1.7.0 — elite Founder/Partner Workspace refinement',
        'v1.8.0 — Production Workspace redesign', 'topbar-context', 'signal-grid', 'pipeline-track',
    )
    organization_source = base_template + profile_template + css_text
    if any(marker not in organization_source for marker in required_organization):
        fail("App-wide organization update is incomplete.")

    admin_dashboard_template = (ROOT / "app" / "templates" / "dashboard_admin.html").read_text(encoding="utf-8", errors="replace")
    partner_dashboard_template = (ROOT / "app" / "templates" / "dashboard_partner.html").read_text(encoding="utf-8", errors="replace")
    leads_template = (ROOT / "app" / "templates" / "leads_list.html").read_text(encoding="utf-8", errors="replace")
    lead_detail_template = (ROOT / "app" / "templates" / "lead_detail.html").read_text(encoding="utf-8", errors="replace")
    inquiries_template = (ROOT / "app" / "templates" / "inquiries.html").read_text(encoding="utf-8", errors="replace")
    workspace_refinement_source = (
        admin_dashboard_template + partner_dashboard_template + leads_template + lead_detail_template +
        inquiries_template + base_template + routes_text + js_text + css_text
    )
    required_workspace_refinement = (
        'metrics.contacted', 'metrics.proposal', 'pipeline-stage-strip', 'workspace-rate', 'operational-table',
        'inbox-summary', 'data-lead-status-form', 'data-status-field', 'syncStatusFields',
        'v1.7.0 — elite Founder/Partner Workspace refinement', 'v1.8.0 — Production Workspace redesign',
    )
    if any(marker not in workspace_refinement_source for marker in required_workspace_refinement):
        fail("v1.8.0 production Workspace redesign is incomplete.")

    partner_ui_files = [
        ROOT / "app" / "templates" / "partners_list.html",
        ROOT / "app" / "templates" / "partner_form.html",
        ROOT / "app" / "templates" / "partner_detail.html",
        ROOT / "app" / "templates" / "partner_created.html",
        ROOT / "app" / "templates" / "partner_password_changed.html",
    ]
    partner_ui = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in partner_ui_files)
    for forbidden in ("Deactivate", "Reactivate", "Suspend", "Disable account", "Archive account", "Founder/Admin", "Founder / Admin", "Employee/Partner", "Employee / Partner", "Employee Partner", "Partner Employee"):
        if forbidden.lower() in partner_ui.lower():
            fail(f"Partner account UI still contains forbidden lifecycle/terminology text: {forbidden}")
    required_partner_ui = ("Partners", "Add Partner", "Change Password", "Delete Permanently", "data-password-toggle", "data-copy-target")
    if any(marker not in partner_ui for marker in required_partner_ui):
        fail("Founder Partner-management UI is incomplete.")
    if "generate password" in partner_ui.lower() or "password generator" in partner_ui.lower():
        fail("Partner account UI still contains forced password generation.")

    app = create_app()
    with app.app_context():
        db = get_db()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            fail(f"Database integrity check failed: {integrity}")

        admin = db.execute("SELECT * FROM users WHERE role='admin' AND active=1 ORDER BY id LIMIT 1").fetchone()
        if not admin:
            fail("No Founder account was found.")

        tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        required_communication = {"messages", "message_attachments", "voice_calls", "voice_call_signals"}
        required_unified = {"website_inquiries", "client_conversations", "client_messages", "client_attachments", "client_notifications", "background_leases"}
        if not required_unified.issubset(tables):
            fail("Unified website inquiry/client conversation database update is incomplete.")
        if not required_communication.issubset(tables):
            fail("Private communication database update is incomplete.")
        call_columns = {row["name"] for row in db.execute("PRAGMA table_info(voice_calls)").fetchall()}
        required_call_columns = {"end_reason", "ended_by_user_id", "caller_seen_at", "receiver_seen_at"}
        if not required_call_columns.issubset(call_columns):
            fail("Simple voice-call database update is incomplete.")
        user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
        required_avatar_columns = {"avatar_stored_name", "avatar_mime_type", "avatar_updated_at"}
        if not required_avatar_columns.issubset(user_columns):
            fail("Per-user profile-picture database migration is incomplete.")
        conversation_columns = {row["name"] for row in db.execute("PRAGMA table_info(client_conversations)").fetchall()}
        required_client_columns = {"first_response_due_at", "first_responded_at", "last_client_message_at", "last_outbound_message_at"}
        if not required_client_columns.issubset(conversation_columns):
            fail("Unified client response-accountability migration is incomplete.")
        client_message_columns = {row["name"] for row in db.execute("PRAGMA table_info(client_messages)").fetchall()}
        if not {"delivery_status", "delivery_error", "sent_by_name_snapshot"}.issubset(client_message_columns):
            fail("Unified client email delivery-state migration is incomplete.")
        migration = db.execute("SELECT MAX(version) v FROM schema_migrations").fetchone()
        if not migration or int(migration["v"] or 0) < 12:
            fail("Founder Partner account-control migration v12 is missing.")
        partner_columns = {row["name"] for row in db.execute("PRAGMA table_info(partners)").fetchall()}
        if not {"full_name_snapshot", "email_snapshot", "deleted_at"}.issubset(partner_columns):
            fail("Partner deletion-history columns are incomplete.")
        partner_user_id_column = next((row for row in db.execute("PRAGMA table_info(partners)").fetchall() if row["name"] == "user_id"), None)
        if not partner_user_id_column or int(partner_user_id_column["notnull"] or 0) != 0:
            fail("Partner deletion migration did not make the authentication link detachable.")
        stale_disabled = db.execute("""SELECT COUNT(*) c FROM partners p JOIN users u ON u.id=p.user_id
            WHERE p.user_id IS NOT NULL AND (p.active<>1 OR u.active<>1)""").fetchone()["c"]
        if stale_disabled:
            fail("Legacy Partner deactivate state still exists after migration.")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            fail("Database foreign-key integrity check failed.")
        stages = [(row["name"], int(row["rate_bp"])) for row in db.execute("SELECT name,rate_bp FROM commission_stages ORDER BY sort_order").fetchall()]
        if stages != [("Founding Partner #1",4000),("Early Partner",3000),("Established Sales Partner",2000),("Standard Partner",1500)]:
            fail("Commission ladder does not match the locked RSF rates.")

        public_client = app.test_client()
        public_home = public_client.get("/", follow_redirects=False)
        public_contact = public_client.get("/contact", follow_redirects=False)
        if public_home.status_code != 200 or "Realty Systems Foundry" not in public_home.get_data(as_text=True):
            fail("Unified public website check failed: home page did not render.")
        if public_contact.status_code != 200 or "Tell us what you need" not in public_contact.get_data(as_text=True):
            fail("Unified public website check failed: contact page did not render.")

        admin_client = app.test_client()
        with admin_client.session_transaction() as session:
            session["user_id"] = admin["id"]
            session["credential"] = session_credential(admin)
            session.permanent = True
        dashboard_page = admin_client.get("/app/", follow_redirects=False)
        dashboard_html = dashboard_page.get_data(as_text=True)
        if dashboard_page.status_code != 200 or "Founder command center" not in dashboard_html or "Partner workload" not in dashboard_html or "Pipeline movement" not in dashboard_html or "Revenue & commissions" not in dashboard_html:
            fail("Founder production dashboard check failed.")

        founder_profile = admin_client.get("/app/profile", follow_redirects=False)
        founder_profile_html = founder_profile.get_data(as_text=True)
        if founder_profile.status_code != 200 or "Founder" not in _visible_text(founder_profile_html) or "profile-picture-manager" not in founder_profile_html or 'name="profile_picture"' not in founder_profile_html:
            fail("Founder profile-picture self-service check failed.")
        if "profile-organized-layout" not in founder_profile_html or "Manage your identity" not in founder_profile_html:
            fail("Founder organized profile check failed.")

        messages_page = admin_client.get("/app/messages", follow_redirects=False)
        if messages_page.status_code != 200 or "Messages" not in messages_page.get_data(as_text=True):
            fail("Founder messaging check failed.")

        client_inbox_page = admin_client.get("/app/inquiries", follow_redirects=False)
        inbox_html = client_inbox_page.get_data(as_text=True)
        if client_inbox_page.status_code != 200 or "Client Inbox" not in inbox_html or "Unclaimed" not in inbox_html:
            fail("Unified client inbox check failed.")
        inbox_template = (ROOT / "app" / "templates" / "inquiries.html").read_text(encoding="utf-8", errors="replace")
        if "Needs attention now" not in inbox_template or "response target" not in inbox_template:
            fail("Unified client response-accountability UI check failed.")
        if "data-client-unread" not in base_template or "setClientUnread" not in js_text:
            fail("Unified client notification check failed.")
        client_template = (ROOT / "app" / "templates" / "client_conversation.html").read_text(encoding="utf-8", errors="replace")
        if 'name="attachments"' not in client_template or "delivery-status" not in client_template or "Automatic client email sync" not in client_template:
            fail("Unified client email/attachment workspace check failed.")

        partner = db.execute(
            """SELECT u.*,p.id partner_id,p.active AS partner_active,cs.name stage_name,cs.rate_bp
               FROM users u JOIN partners p ON p.user_id=u.id
               JOIN commission_stages cs ON cs.id=p.commission_stage_id
               WHERE u.role='partner' AND p.user_id IS NOT NULL ORDER BY p.id LIMIT 1"""
        ).fetchone()

        if partner:
            client = app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = partner["id"]
                session["credential"] = session_credential(partner)
                session.permanent = True

            if client.get("/app/admin/partners", follow_redirects=False).status_code != 403:
                fail("Partner privacy check failed: Founder-only page was not blocked.")

            partner_dashboard = client.get("/app/", follow_redirects=False)
            partner_dashboard_html = partner_dashboard.get_data(as_text=True)
            if partner_dashboard.status_code != 200 or "Partner command center" not in partner_dashboard_html or "Commission" not in partner_dashboard_html or "Lead progress" not in partner_dashboard_html or "Sales & commissions" not in partner_dashboard_html or "What needs attention" not in partner_dashboard_html:
                fail("Partner production dashboard check failed.")

            partner_commissions = client.get("/app/commissions", follow_redirects=False)
            partner_commissions_html = partner_commissions.get_data(as_text=True)
            if partner_commissions.status_code != 200 or f"{partner['rate_bp'] / 100:g}%" not in partner_commissions_html:
                fail("Partner commission-rate check failed.")
            for hidden_stage in ("Founding Partner #1", "Early Partner", "Established Sales Partner", "Standard Partner"):
                if hidden_stage != partner["stage_name"] and hidden_stage in partner_commissions_html:
                    fail("Partner commission privacy check failed: another commission level was visible.")

            own_messages = client.get(f"/app/messages/{partner['partner_id']}", follow_redirects=False)
            partner_message_html = own_messages.get_data(as_text=True)
            if own_messages.status_code != 200 or ">Founder<" not in partner_message_html or "data-start-call" not in partner_message_html:
                fail("Partner messaging check failed: own Founder conversation or simple Call action was not available.")
            if "founder-avatar" not in partner_message_html or "message-peer-photo" not in partner_message_html:
                fail("Partner messaging check failed: Founder profile picture was not available.")
            if "message-conversations" in partner_message_html:
                fail("Partner messaging privacy check failed: Founder partner list was visible to a Partner.")
            other_partner = db.execute("SELECT id FROM partners WHERE id<>? ORDER BY id LIMIT 1", (partner["partner_id"],)).fetchone()
            if other_partner and client.get(f"/app/messages/{other_partner['id']}", follow_redirects=False).status_code != 404:
                fail("Partner messaging privacy check failed: another partner conversation was visible.")

            profile = client.get("/app/profile", follow_redirects=False)
            profile_text = profile.get_data(as_text=True)
            if profile.status_code != 200 or "Change password" in profile_text or "Current password" in profile_text:
                fail("Partner password-control check failed: partner password controls are visible.")
            if "profile-picture-manager" not in profile_text or 'name="profile_picture"' not in profile_text or "Upload photo" not in profile_text:
                fail("Partner profile-picture self-service check failed.")
            match = re.search(r'name="csrf_token" value="([^"]+)"', profile_text)
            if not match:
                fail("Partner profile check failed: CSRF token was not found.")
            blocked_change = client.post(
                "/app/profile",
                data={
                    "csrf_token": match.group(1),
                    "action": "password",
                    "current_password": "not-used",
                    "new_password": "BlockedPartnerChange123!",
                    "confirm_password": "BlockedPartnerChange123!",
                },
                follow_redirects=False,
            )
            if blocked_change.status_code != 403:
                fail("Partner password-control check failed: backend password change was not blocked.")

        verify_founder_partner_account_management(db)

    print("Installed system verified: database OK, Founder account OK, compact Account & Security OK, exact Founder password change OK, Founder one-time password show/hide/copy OK, old Founder password/session invalidation OK, Founder-only Partner management OK, Partner create/view/edit OK, exact Founder-chosen Partner passwords OK, Partner password reset/session invalidation OK, Partner self-service password change blocked OK, forged Founder actions blocked OK, cross-Partner privacy OK, permanent Partner delete confirmation OK, permanent Partner authentication removal OK, deleted Partner login blocked OK, historical business records preserved OK, database integrity/foreign keys OK, CSRF OK, trusted hosts OK, session security OK, security headers OK, RSF Emerald + Champagne UI OK, desktop launchers OK, unified public website OK, Partner Workspace OK.")


if __name__ == "__main__":
    main()
