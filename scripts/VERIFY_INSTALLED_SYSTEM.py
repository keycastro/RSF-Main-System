"""Verify the installed RSF system without changing passwords or business records."""
from __future__ import annotations

import os
import html
import hashlib
import json
from io import BytesIO

import re
import tempfile
from datetime import datetime, timezone
import sys
from pathlib import Path

os.environ["RSF_DISABLE_BACKGROUND"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.db import get_db
from app.auth import session_credential, hash_password
from app.credential_vault import decrypt_password
from werkzeug.security import check_password_hash


def fail(message: str) -> None:
    raise SystemExit(message)


def verify_project_layout() -> None:
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    if version != "1.11.2":
        fail(f"Release version mismatch: expected 1.11.2, found {version or 'empty'}.")
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



def _csrf_from(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    if not match:
        fail("CSRF verification token was not rendered.")
    return match.group(1)


def _login(client, name: str, password: str):
    page = client.get("/app/login", follow_redirects=False)
    html_text = page.get_data(as_text=True)
    if 'name="name"' not in html_text or 'name="email"' in html_text:
        fail("Workspace login is not Name + Password only.")
    token = _csrf_from(page)
    return client.post(
        "/app/login",
        data={"csrf_token": token, "name": name, "password": password},
        follow_redirects=False,
    )


def verify_partner_account_management() -> None:
    """Exercise destructive account behavior only inside an isolated disposable database."""
    with tempfile.TemporaryDirectory(prefix="rsf-partner-verifier-") as temp_name:
        temp = Path(temp_name)
        db_path = temp / "account-management.db"
        test_app = create_app({
            "TESTING": True,
            "DATABASE_URL": "",
            "DATABASE": str(db_path),
            "SECRET_KEY": "rsf-isolated-verifier-secret",
            "MESSAGE_UPLOAD_DIR": str(temp / "message_uploads"),
            "PROFILE_PICTURE_DIR": str(temp / "profile_pictures"),
            "CLIENT_ATTACHMENT_DIR": str(temp / "client_attachments"),
            "BACKUP_DIR": str(temp / "backups"),
            "TRUSTED_HOSTS": ["localhost", "127.0.0.1"],
        })

        founder_name = "Verifier Founder"
        founder_email = "founder-verifier@example.invalid"
        founder_password = "founder-verifier-password"
        founder_new_password = "q"
        partner_name = "Verifier Partner"
        partner_email = "partner-verifier@example.invalid"
        exact_password = "tiny"  # Intentionally weak: exact Founder choice must still be accepted.
        reset_password = "z"     # Same requirement, including one-character passwords.
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        with test_app.app_context():
            db = get_db()
            stage_rows = db.execute(
                "SELECT name,rate_bp FROM commission_stages WHERE active=1 ORDER BY sort_order"
            ).fetchall()
            ladder = [(row["name"], row["rate_bp"]) for row in stage_rows]
            if ladder != [
                ("Founding Partner #1", 4000),
                ("Early Partner", 3000),
                ("Established Sales Partner", 2000),
                ("Standard Partner", 1500),
            ]:
                fail("Commission ladder changed unexpectedly.")
            founder_id = db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'admin',1,0,?,?)""",
                (founder_name, founder_email, hash_password(founder_password), now, now),
            ).lastrowid
            other_user_id = db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'partner',1,0,?,?)""",
                ("Other Verifier Partner", "other-verifier@example.invalid", hash_password("other"), now, now),
            ).lastrowid
            first_stage = db.execute("SELECT id FROM commission_stages ORDER BY sort_order LIMIT 1").fetchone()["id"]
            other_partner_id = db.execute(
                """INSERT INTO partners(user_id,commission_stage_id,phone,notes,joined_at,active,account_deleted_at,historical_name)
                   VALUES (?,?,?,?,?,1,NULL,?)""",
                (other_user_id, first_stage, "", "", now, "Other Verifier Partner"),
            ).lastrowid
            other_lead_id = db.execute(
                """INSERT INTO leads(owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,website,website_domain,lead_source,summary_notes,status,lost_reason,demo_at,registered_at,last_activity_at,created_by_user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'NEW','',NULL,?,?,?)""",
                (other_partner_id, "Other Company", "other company", "Other Contact", "other contact", "", "", "", "", "", "", "Verifier", "", now, now, other_user_id),
            ).lastrowid
            db.commit()

        founder_client = test_app.test_client()
        founder_login = _login(founder_client, founder_name, founder_password)
        if founder_login.status_code != 302 or "/app/" not in founder_login.headers.get("Location", ""):
            fail("Founder Name + Password login verification failed.")
        email_login_client = test_app.test_client()
        if _login(email_login_client, founder_email, founder_password).status_code == 302:
            fail("Old email login still works for a workspace account.")
        with test_app.app_context():
            db = get_db()
            seeded = db.execute("SELECT encrypted_password FROM account_password_vault WHERE user_id=?", (founder_id,)).fetchone()
            if not seeded or seeded["encrypted_password"] == founder_password:
                fail("Successful Founder login did not initialize an encrypted current-password vault entry.")
            try:
                seeded_password = decrypt_password(seeded["encrypted_password"])
            except RuntimeError:
                fail("Founder login-seeded current-password vault entry could not be decrypted.")
            if seeded_password != founder_password:
                fail("Founder login-seeded vault entry does not match the exact authenticated password.")

        account_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        account_html = account_page.get_data(as_text=True)
        required_account = (
            "Account &amp; Security", "Founder Account", "Partner Accounts", "New Password", "Confirm Password",
            "Current Password", "data-vault-reveal", "data-vault-copy", "data-password-vault-url",
            "compact-password-form", "partner-security-list", "security-change-disclosure",
        )
        if account_page.status_code != 200 or any(marker not in account_html for marker in required_account):
            fail("Simplified Founder Account & Security workspace is incomplete.")
        if 'name="current_password"' in account_html:
            fail("Account & Security unexpectedly asks the Founder to re-enter the current password in the change form.")
        if founder_name not in account_html:
            fail("Founder Name is missing from Account & Security.")
        if founder_email in account_html:
            fail("Founder account email is still visible in Account & Security.")
        for forbidden in ("Founder/Admin", "Founder / Admin", "Founder Admin", "Employee", "Staff", "Deactivate", "Suspend", "Archive"):
            if forbidden.lower() in account_html.lower():
                fail(f"Obsolete account terminology is visible in Account & Security: {forbidden}")
        for nag in ("too weak", "stronger password", "add a symbol", "uppercase", "lowercase", "password strength", "12+ characters"):
            if nag in account_html.lower():
                fail(f"Password-strength rule is visible in Account & Security: {nag}")

        stale_founder = test_app.test_client()
        if _login(stale_founder, founder_name, founder_password).status_code != 302:
            fail("Founder stale-session setup failed.")
        if founder_client.post(
            "/app/admin/settings/account-security/founder-password",
            data={"new_password": founder_new_password, "confirm_password": founder_new_password},
            follow_redirects=False,
        ).status_code != 400:
            fail("CSRF protection failed on Founder password change.")
        founder_change = founder_client.post(
            "/app/admin/settings/account-security/founder-password",
            data={"csrf_token": _csrf_from(account_page), "new_password": founder_new_password, "confirm_password": founder_new_password},
            follow_redirects=False,
        )
        founder_changed_html = founder_change.get_data(as_text=True)
        if founder_change.status_code != 200 or 'data-vault-reveal' not in founder_changed_html or 'data-vault-copy' not in founder_changed_html:
            fail("Founder password change did not return the Founder password-visibility workspace.")
        reveal_csrf = _csrf_from(founder_change)
        no_csrf_reveal = founder_client.post(
            "/app/admin/settings/account-security/reveal-password",
            data={"user_id": str(founder_id)},
            follow_redirects=False,
        )
        if no_csrf_reveal.status_code != 400:
            fail("CSRF protection failed on Founder password reveal.")
        founder_reveal = founder_client.post(
            "/app/admin/settings/account-security/reveal-password",
            data={"csrf_token": reveal_csrf, "user_id": str(founder_id)},
            follow_redirects=False,
        )
        if founder_reveal.status_code != 200 or founder_reveal.get_json().get("password") != founder_new_password:
            fail("Founder current password is not persistently revealable from Account & Security.")
        if "no-store" not in founder_reveal.headers.get("Cache-Control", ""):
            fail("Founder password reveal response is cacheable.")
        with test_app.app_context():
            row = get_db().execute("SELECT password_hash FROM users WHERE lower(trim(full_name))=lower(trim(?))", (founder_name,)).fetchone()
            if not row or not check_password_hash(row["password_hash"], founder_new_password) or check_password_hash(row["password_hash"], founder_password):
                fail("Founder password was not replaced exactly.")
        stale_response = stale_founder.get("/app/admin/settings/account-security", follow_redirects=False)
        if stale_response.status_code != 302 or "/app/login" not in stale_response.headers.get("Location", ""):
            fail("Older Founder session was not invalidated after password change.")
        old_founder = test_app.test_client()
        if _login(old_founder, founder_name, founder_password).status_code == 302:
            fail("Old Founder password still works after password change.")
        founder_after_get = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        if founder_after_get.status_code != 200:
            fail("Current Founder session was not rebound after password change.")
        founder_after_html = founder_after_get.get_data(as_text=True)
        if 'data-vault-reveal' not in founder_after_html or 'value="' + founder_new_password + '"' in founder_after_html:
            fail("Founder password visibility control is missing or plaintext leaked into the initial page HTML.")
        founder_reveal_again = founder_client.post(
            "/app/admin/settings/account-security/reveal-password",
            data={"csrf_token": _csrf_from(founder_after_get), "user_id": str(founder_id)},
            follow_redirects=False,
        )
        if founder_reveal_again.status_code != 200 or founder_reveal_again.get_json().get("password") != founder_new_password:
            fail("Founder current password was not retained in the encrypted visibility vault.")
        new_founder = test_app.test_client()
        if _login(new_founder, founder_name, founder_new_password).status_code != 302:
            fail("New exact Founder password does not work.")
        founder_password = founder_new_password

        founder_profile = founder_client.get("/app/profile", follow_redirects=False)
        founder_profile_html = founder_profile.get_data(as_text=True)
        if 'name="current_password"' in founder_profile_html or 'name="new_password"' in founder_profile_html:
            fail("Founder password controls are still scattered on Profile.")
        if "Account &amp; Security" in founder_profile_html or "Open Account" in founder_profile_html:
            fail("Founder Profile still duplicates Account & Security controls/navigation.")

        partners_page = founder_client.get("/app/admin/partners", follow_redirects=False)
        partners_html = partners_page.get_data(as_text=True)
        if partners_page.status_code != 200 or "Partners" not in partners_html or "Create Partner" not in partners_html:
            fail("Founder Partners management page verification failed.")
        for forbidden in ("Founder/Admin", "Founder / Admin", "Founder Admin", "Employee", "Deactivate", "Reactivate", "Suspend", "Disable account", "Archive account"):
            if forbidden.lower() in partners_html.lower():
                fail(f"Obsolete account terminology is visible in Partners: {forbidden}")

        create_page = founder_client.get("/app/admin/partners/new", follow_redirects=False)
        create_html = create_page.get_data(as_text=True)
        if create_page.status_code != 200 or "data-password-toggle" not in create_html or "data-copy-target" not in create_html or 'name="partner_password"' not in create_html:
            fail("Founder create-Partner password reveal/copy controls are missing.")
        if 'name="email"' in create_html:
            fail("Partner account creation still asks for email.")
        for nag in ("too weak", "stronger password", "add a symbol", "uppercase", "lowercase", "password strength"):
            if nag in create_html.lower():
                fail(f"Partner password-strength nagging is still present: {nag}")

        create_result = founder_client.post(
            "/app/admin/partners/new",
            data={
                "csrf_token": _csrf_from(create_page),
                "full_name": partner_name,
                "phone": "",
                "commission_stage_id": str(first_stage),
                "partner_password": exact_password,
                "notes": "Disposable verifier account",
            },
            follow_redirects=False,
        )
        created_html = create_result.get_data(as_text=True)
        if (create_result.status_code != 200 or exact_password not in created_html or 'id="created_password"' not in created_html
                or "data-password-toggle" not in created_html or "data-copy-target" not in created_html):
            fail("Founder create-Partner exact-password result verification failed.")

        with test_app.app_context():
            db = get_db()
            created = db.execute(
                """SELECT u.*,p.id partner_id,p.commission_stage_id,p.historical_name
                   FROM users u JOIN partners p ON p.user_id=u.id WHERE lower(trim(u.full_name))=lower(trim(?))""",
                (partner_name,),
            ).fetchone()
            if not created or not check_password_hash(created["password_hash"], exact_password):
                fail("Exact Founder-chosen Partner password was not stored as a valid hash.")
            if created["password_hash"] == exact_password:
                fail("Partner password was stored as plaintext.")
            partner_id = int(created["partner_id"])
            partner_user_id = int(created["id"])

        duplicate_page = founder_client.get("/app/admin/partners/new", follow_redirects=False)
        duplicate_result = founder_client.post(
            "/app/admin/partners/new",
            data={
                "csrf_token": _csrf_from(duplicate_page),
                "full_name": partner_name.upper(),
                "commission_stage_id": str(first_stage),
                "partner_password": "duplicate",
            },
            follow_redirects=True,
        )
        if duplicate_result.status_code != 200 or "This name is already in use." not in duplicate_result.get_data(as_text=True):
            fail("Case-insensitive duplicate Partner Name was not blocked.")

        partner_client = test_app.test_client()
        exact_login = _login(partner_client, partner_name.upper(), exact_password)
        if exact_login.status_code != 302:
            fail("New Partner cannot sign in with case-insensitive Name + exact Founder-chosen password.")
        if partner_client.get("/app/", follow_redirects=False).status_code != 200:
            fail("Partner Workspace login flow verification failed.")

        detail_page = founder_client.get(f"/app/admin/partners/{partner_id}", follow_redirects=False)
        detail_html = detail_page.get_data(as_text=True)
        if detail_page.status_code != 200 or "Partner details" not in detail_html or "Login &amp; Password" not in detail_html:
            fail("Founder Partner detail/edit handoff to credential management is incomplete.")
        if "Change password" in detail_html or "Delete Partner Permanently" in detail_html:
            fail("Partner credential controls are still scattered on Partner detail.")
        edit_result = founder_client.post(
            f"/app/admin/partners/{partner_id}",
            data={
                "csrf_token": _csrf_from(detail_page),
                "full_name": "Verifier Partner Edited",
                "phone": "123",
                "commission_stage_id": str(first_stage),
                "notes": "Edited by verifier",
            },
            follow_redirects=False,
        )
        if edit_result.status_code != 302:
            fail("Founder could not edit Partner information.")
        with test_app.app_context():
            row = get_db().execute(
                "SELECT u.full_name,p.phone,p.historical_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=?",
                (partner_id,),
            ).fetchone()
            if not row or row["full_name"] != "Verifier Partner Edited" or row["phone"] != "123" or row["historical_name"] != "Verifier Partner Edited":
                fail("Founder Partner edit did not persist correctly.")

        # CSRF must reject a forged Founder write even when the Founder session is valid.
        if founder_client.post(
            f"/app/admin/partners/{partner_id}/reset-password",
            data={"partner_password": "forged", "confirm_partner_password": "forged"},
            follow_redirects=False,
        ).status_code != 400:
            fail("CSRF protection failed on Partner password reset.")

        reset_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        reset_html_before = reset_page.get_data(as_text=True)
        if partner_email in reset_html_before:
            fail("Partner account email is still visible in Account & Security.")
        required_partner_actions = ("Current Password", "Change password", "Delete Partner", "data-account-disclosure", "data-vault-reveal", "data-vault-copy", f'id="partner-password-panel-{partner_id}"')
        if f'id="partner-{partner_id}"' not in reset_html_before or any(marker not in reset_html_before for marker in required_partner_actions):
            fail("Partner credential actions are incomplete in Account & Security.")
        if ">View<" in reset_html_before or ">Edit<" in reset_html_before or "Create Partner" in reset_html_before:
            fail("Account & Security still duplicates general Partner management actions.")
        reset_result = founder_client.post(
            f"/app/admin/partners/{partner_id}/reset-password",
            data={"csrf_token": _csrf_from(reset_page), "partner_password": reset_password, "confirm_partner_password": reset_password},
            follow_redirects=False,
        )
        reset_html = reset_result.get_data(as_text=True)
        if reset_result.status_code != 200 or 'data-vault-reveal' not in reset_html or 'data-vault-copy' not in reset_html:
            fail("Partner password reset did not return persistent Founder password controls.")
        partner_reveal = founder_client.post(
            "/app/admin/settings/account-security/reveal-password",
            data={"csrf_token": _csrf_from(reset_result), "user_id": str(partner_user_id)},
            follow_redirects=False,
        )
        if partner_reveal.status_code != 200 or partner_reveal.get_json().get("password") != reset_password:
            fail("Founder cannot reveal the current Partner password after reset.")
        partner_after_get = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        partner_after_html = partner_after_get.get_data(as_text=True)
        # A one-character verifier password (for example "z") may naturally occur
        # elsewhere in ordinary HTML. Only fail if the exact plaintext password was
        # embedded as a form/input value on the initial page. The real password is
        # fetched only after a Founder-only reveal/copy request.
        escaped_reset_password = html.escape(reset_password, quote=True)
        if f'value="{escaped_reset_password}"' in partner_after_html:
            fail("Partner plaintext password leaked into the initial Account & Security HTML.")
        partner_reveal_again = founder_client.post(
            "/app/admin/settings/account-security/reveal-password",
            data={"csrf_token": _csrf_from(partner_after_get), "user_id": str(partner_user_id)},
            follow_redirects=False,
        )
        if partner_reveal_again.status_code != 200 or partner_reveal_again.get_json().get("password") != reset_password:
            fail("Partner current password was not retained in the encrypted Founder visibility vault.")
        with test_app.app_context():
            db = get_db()
            changed = db.execute("SELECT password_hash FROM users WHERE id=?", (partner_user_id,)).fetchone()
            vault_row = db.execute("SELECT encrypted_password FROM account_password_vault WHERE user_id=?", (partner_user_id,)).fetchone()
            if not changed or not check_password_hash(changed["password_hash"], reset_password) or check_password_hash(changed["password_hash"], exact_password):
                fail("Partner password reset did not replace the old password exactly.")
            if not vault_row or vault_row["encrypted_password"] == reset_password:
                fail("Partner password visibility vault is missing or storing plaintext.")
            try:
                stored_partner_password = decrypt_password(vault_row["encrypted_password"])
            except RuntimeError:
                fail("Partner password visibility vault cannot decrypt the stored credential.")
            if stored_partner_password != reset_password:
                fail("Partner password visibility vault does not contain the exact current password.")

        # A password reset invalidates existing Partner sessions because session credentials bind to the hash.
        stale_session = partner_client.get("/app/", follow_redirects=False)
        if stale_session.status_code != 302 or "/app/login" not in stale_session.headers.get("Location", ""):
            fail("Partner session was not invalidated after password reset.")
        old_client = test_app.test_client()
        if _login(old_client, "Verifier Partner Edited", exact_password).status_code == 302:
            fail("Old Partner password still works after reset.")
        partner_client = test_app.test_client()
        if _login(partner_client, "Verifier Partner Edited", reset_password).status_code != 302:
            fail("New exact Partner password does not work after reset.")

        partner_profile = partner_client.get("/app/profile", follow_redirects=False)
        partner_profile_html = partner_profile.get_data(as_text=True)
        if "Change password" in partner_profile_html or "Current password" in partner_profile_html:
            fail("Partner self-service password controls are visible.")
        partner_csrf = _csrf_from(partner_profile)
        upload_result = partner_client.post(
            "/app/profile",
            data={
                "csrf_token": partner_csrf,
                "action": "avatar",
                "profile_picture": (BytesIO(b"\x89PNG\r\n\x1a\nRSF-VERIFIER"), "partner-avatar.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        if upload_result.status_code not in (302, 303):
            fail("Partner profile-picture upload action failed in the disposable account audit.")
        uploaded_picture = partner_client.get(f"/app/profile-picture/{partner_user_id}", follow_redirects=False)
        try:
            if uploaded_picture.status_code != 200 or uploaded_picture.mimetype != "image/png":
                fail("Partner uploaded profile picture could not be read back in the disposable account audit.")
            # Fully consume and explicitly close the file-backed response before
            # Windows tries to remove the disposable profile-picture directory.
            # Without this, Python/Flask can keep the PNG handle open until GC.
            uploaded_picture.get_data()
        finally:
            uploaded_picture.close()
        refreshed_profile = partner_client.get("/app/profile", follow_redirects=False)
        remove_result = partner_client.post(
            "/app/profile",
            data={"csrf_token": _csrf_from(refreshed_profile), "action": "avatar_remove"},
            follow_redirects=False,
        )
        if remove_result.status_code not in (302, 303):
            fail("Partner profile-picture remove action failed in the disposable account audit.")
        blocked_self_change = partner_client.post(
            "/app/profile",
            data={
                "csrf_token": partner_csrf,
                "action": "password",
                "current_password": reset_password,
                "new_password": "self-change",
                "confirm_password": "self-change",
            },
            follow_redirects=False,
        )
        if blocked_self_change.status_code != 403:
            fail("Partner self-service password change is not blocked at the backend.")

        # Direct URL and forged Founder-account actions must be denied to Partners.
        if partner_client.get("/app/admin/partners", follow_redirects=False).status_code != 403:
            fail("Partner can access Founder Partners management.")
        if partner_client.get("/app/admin/settings/account-security", follow_redirects=False).status_code != 403:
            fail("Partner can access Founder Account & Security.")
        if partner_client.get(f"/app/admin/partners/{other_partner_id}", follow_redirects=False).status_code != 403:
            fail("Partner can view another Partner through a Founder route.")
        for path, payload in (
            ("/app/admin/settings/account-security/founder-password", {"new_password": "forged", "confirm_password": "forged"}),
            ("/app/admin/settings/account-security/reveal-password", {"user_id": str(founder_id)}),
            ("/app/admin/partners/new", {"full_name": "Forged", "commission_stage_id": str(first_stage), "partner_password": "x"}),
            (f"/app/admin/partners/{other_partner_id}/reset-password", {"partner_password": "x", "confirm_partner_password": "x"}),
            (f"/app/admin/partners/{other_partner_id}/delete", {}),
        ):
            forged = {"csrf_token": partner_csrf, **payload}
            if partner_client.post(path, data=forged, follow_redirects=False).status_code != 403:
                fail(f"Partner forged Founder action was not blocked: {path}")
        if partner_client.get(f"/app/messages/{other_partner_id}", follow_redirects=False).status_code != 404:
            fail("Partner can access another Partner's private messages.")
        if partner_client.get(f"/app/leads/{other_lead_id}", follow_redirects=False).status_code != 404:
            fail("Partner can access another Partner's private lead data.")

        # Seed representative business history, then delete only the disposable account.
        with test_app.app_context():
            db = get_db()
            created = db.execute("SELECT * FROM users WHERE id=?", (partner_user_id,)).fetchone()
            stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            lead_id = db.execute(
                """INSERT INTO leads(owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,website,website_domain,lead_source,summary_notes,status,lost_reason,demo_at,registered_at,last_activity_at,created_by_user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'WON','',NULL,?,?,?)""",
                (partner_id, "Verifier Client", "verifier client", "Client", "client", "client@example.invalid", "client@example.invalid", "", "", "", "", "Verifier", "", stamp, stamp, partner_user_id),
            ).lastrowid
            note_id = db.execute(
                "INSERT INTO lead_notes(lead_id,author_user_id,body,created_at) VALUES (?,?,?,?)",
                (lead_id, partner_user_id, "Historical note", stamp),
            ).lastrowid
            followup_id = db.execute(
                """INSERT INTO followups(lead_id,owner_partner_id,title,due_at,notes,status,completed_at,created_by_user_id,created_at,updated_at)
                   VALUES (?,?,?,?,?,'COMPLETED',?,?,?,?)""",
                (lead_id, partner_id, "Historical follow-up", stamp, "", stamp, partner_user_id, stamp, stamp),
            ).lastrowid
            sale_id = db.execute(
                """INSERT INTO sales(lead_id,partner_id,client_name,product_service,deal_amount_cents,invoiced_cents,collected_cents,qualifying_revenue_cents,payment_status,sale_date,notes,created_by_user_id,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (lead_id, partner_id, "Verifier Client", "Verifier Service", 10000, 10000, 10000, 10000, "PAID", stamp[:10], "", partner_user_id, stamp, stamp),
            ).lastrowid
            commission_id = db.execute(
                """INSERT INTO commissions(sale_id,partner_id,stage_name_snapshot,rate_bp_snapshot,qualifying_revenue_cents,adjustment_cents,commission_amount_cents,status,approval_date,paid_date,notes,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,'PAID',?,?,?, ?,?)""",
                (sale_id, partner_id, "Founding Partner #1", 4000, 10000, 0, 4000, stamp, stamp, "", stamp, stamp),
            ).lastrowid
            message_id = db.execute(
                "INSERT INTO messages(partner_id,sender_user_id,body,founder_read_at,partner_read_at,created_at) VALUES (?,?,?,?,?,?)",
                (partner_id, partner_user_id, "Historical private message", None, stamp, stamp),
            ).lastrowid
            attachment_id = db.execute(
                """INSERT INTO message_attachments(message_id,partner_id,original_name,stored_name,mime_type,size_bytes,created_at,data_blob)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (message_id, partner_id, "history.txt", "verifier-history.txt", "text/plain", 7, stamp, b"history"),
            ).lastrowid
            inquiry_id = db.execute(
                """INSERT INTO website_inquiries(created_at,updated_at,name,email,email_norm,company,message,status,claimed_by_partner_id,claimed_at,lead_id,source_type,source_slug,source_title,source_action)
                   VALUES (?,?,?,?,?,?,?,'CLAIMED',?,?,?,?,?,?,?)""",
                (stamp, stamp, "Verifier Client", "client@example.invalid", "client@example.invalid", "Verifier Client", "Inquiry", partner_id, stamp, lead_id, "website", "contact", "Contact", "submit"),
            ).lastrowid
            conversation_id = db.execute(
                """INSERT INTO client_conversations(inquiry_id,lead_id,owner_partner_id,client_name,client_email,company,subject,status,created_at,updated_at,first_response_due_at,first_responded_at,last_client_message_at,last_outbound_message_at)
                   VALUES (?,?,?,?,?,?,?,'ACTIVE',?,?,?,?,?,?)""",
                (inquiry_id, lead_id, partner_id, "Verifier Client", "client@example.invalid", "Verifier Client", "Verifier conversation", stamp, stamp, stamp, stamp, stamp, stamp),
            ).lastrowid
            db.execute("UPDATE website_inquiries SET client_conversation_id=? WHERE id=?", (conversation_id, inquiry_id))
            client_message_id = db.execute(
                """INSERT INTO client_messages(conversation_id,direction,channel,sender_email,recipient_email,subject,body,sent_by_user_id,external_message_id,in_reply_to,created_at,delivery_status,delivery_error)
                   VALUES (?,'OUTBOUND','EMAIL',?,?,?,?,?,'','',?,'SENT','')""",
                (conversation_id, founder_email, "client@example.invalid", "Verifier", "Historical client message", partner_user_id, stamp),
            ).lastrowid
            client_attachment_id = db.execute(
                """INSERT INTO client_attachments(message_id,original_name,stored_name,mime_type,size_bytes,created_at,data_blob)
                   VALUES (?,?,?,?,?,?,?)""",
                (client_message_id, "client-history.txt", "verifier-client-history.txt", "text/plain", 7, stamp, b"history"),
            ).lastrowid
            db.commit()

        delete_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        delete_csrf = _csrf_from(delete_page)
        missing_confirmation = founder_client.post(
            f"/app/admin/partners/{partner_id}/delete",
            data={"csrf_token": delete_csrf},
            follow_redirects=False,
        )
        if missing_confirmation.status_code != 400:
            fail("Permanent Partner deletion did not require explicit confirmation.")
        # Active client work must block deletion until a replacement Partner is chosen.
        blocked_delete = founder_client.post(
            f"/app/admin/partners/{partner_id}/delete",
            data={"csrf_token": delete_csrf, "confirm_delete": "1"},
            follow_redirects=False,
        )
        if blocked_delete.status_code != 302:
            fail("Partner deletion with active work did not stop safely.")
        with test_app.app_context():
            db = get_db()
            if not db.execute("SELECT 1 FROM users WHERE id=?", (partner_user_id,)).fetchone():
                fail("Blocked Partner deletion removed the account before active work was moved.")

        delete_page = founder_client.get("/app/admin/settings/account-security", follow_redirects=False)
        delete_csrf = _csrf_from(delete_page)
        delete_result = founder_client.post(
            f"/app/admin/partners/{partner_id}/delete",
            data={"csrf_token": delete_csrf, "confirm_delete": "1", "move_active_to_partner_id": str(other_partner_id)},
            follow_redirects=False,
        )
        if delete_result.status_code != 302 or "/app/admin/settings/account-security" not in delete_result.headers.get("Location", ""):
            fail("Founder Partner deletion with active-work transfer failed from Account & Security.")

        with test_app.app_context():
            db = get_db()
            if db.execute("SELECT 1 FROM users WHERE id=?", (partner_user_id,)).fetchone():
                fail("Permanent Partner deletion left the login/account row in users.")
            stub = db.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()
            if not stub or stub["user_id"] is not None or not stub["account_deleted_at"] or stub["active"] != 0:
                fail("Deleted Partner historical attribution was not safely detached from the account.")
            if stub["historical_name"] != "Verifier Partner Edited" or stub["phone"] or stub["notes"]:
                fail("Deleted Partner historical record retained profile/account details unexpectedly.")
            moved_lead = db.execute("SELECT owner_partner_id FROM leads WHERE id=?", (lead_id,)).fetchone()
            moved_conversation = db.execute("SELECT owner_partner_id FROM client_conversations WHERE id=?", (conversation_id,)).fetchone()
            moved_inquiry = db.execute("SELECT claimed_by_partner_id FROM website_inquiries WHERE id=?", (inquiry_id,)).fetchone()
            historical_sale = db.execute("SELECT partner_id FROM sales WHERE id=?", (sale_id,)).fetchone()
            historical_commission = db.execute("SELECT partner_id FROM commissions WHERE id=?", (commission_id,)).fetchone()
            if not moved_lead or moved_lead["owner_partner_id"] != other_partner_id:
                fail("Active Lead was not moved before Partner deletion.")
            if not moved_conversation or moved_conversation["owner_partner_id"] != other_partner_id:
                fail("Active client conversation was not moved before Partner deletion.")
            if not moved_inquiry or moved_inquiry["claimed_by_partner_id"] != other_partner_id:
                fail("Claimed inquiry was not moved before Partner deletion.")
            if not historical_sale or historical_sale["partner_id"] != partner_id:
                fail("Partner deletion changed historical Sale ownership.")
            if not historical_commission or historical_commission["partner_id"] != partner_id:
                fail("Partner deletion changed historical commission ownership.")
            preserved = {
                "leads": ("id", lead_id),
                "lead_notes": ("id", note_id),
                "followups": ("id", followup_id),
                "sales": ("id", sale_id),
                "commissions": ("id", commission_id),
                "messages": ("id", message_id),
                "message_attachments": ("id", attachment_id),
                "website_inquiries": ("id", inquiry_id),
                "client_conversations": ("id", conversation_id),
                "client_messages": ("id", client_message_id),
                "client_attachments": ("id", client_attachment_id),
            }
            for table, (column, value) in preserved.items():
                if not db.execute(f'SELECT 1 FROM "{table}" WHERE "{column}"=?', (value,)).fetchone():
                    fail(f"Permanent Partner deletion destroyed historical business data: {table}")
            for table, column in (
                ("leads", "created_by_user_id"),
                ("lead_notes", "author_user_id"),
                ("followups", "created_by_user_id"),
                ("sales", "created_by_user_id"),
                ("messages", "sender_user_id"),
                ("client_messages", "sent_by_user_id"),
            ):
                if db.execute(f'SELECT 1 FROM "{table}" WHERE "{column}"=?', (partner_user_id,)).fetchone():
                    fail(f"Deleted user identity remains attached in {table}.{column}.")
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                fail("Database integrity failed after permanent Partner deletion.")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                fail("Foreign-key integrity failed after permanent Partner deletion.")

        deleted_client = test_app.test_client()
        if _login(deleted_client, "Verifier Partner Edited", reset_password).status_code == 302:
            fail("Deleted Partner can still log in.")
        historical_thread = founder_client.get(f"/app/messages/{partner_id}", follow_redirects=False)
        if historical_thread.status_code != 200 or "Historical private message" not in historical_thread.get_data(as_text=True):
            fail("Founder cannot view deleted Partner message history.")

        internal = founder_client.get("/app/admin/partners", follow_redirects=False)
        headers = internal.headers
        if headers.get("X-Frame-Options") != "DENY" or headers.get("X-Content-Type-Options") != "nosniff" or "frame-ancestors 'none'" not in headers.get("Content-Security-Policy", ""):
            fail("Security header verification failed.")
        if test_app.config.get("SESSION_COOKIE_HTTPONLY") is not True or test_app.config.get("SESSION_COOKIE_SAMESITE") != "Lax":
            fail("Session-cookie security configuration is incomplete.")
        hostile = founder_client.get("/", headers={"Host": "untrusted.invalid"}, follow_redirects=False)
        if hostile.status_code != 400:
            fail("Trusted-host protection failed.")



def verify_controlled_repair_regressions() -> None:
    """Check the specific v1.11.0 fixes inside a disposable database."""
    with tempfile.TemporaryDirectory(prefix="rsf-repair-verifier-") as temp_name:
        temp = Path(temp_name)
        test_app = create_app({
            "TESTING": True,
            "DATABASE_URL": "",
            "DATABASE": str(temp / "repair.db"),
            "SECRET_KEY": "rsf-repair-verifier-secret",
            "CREDENTIAL_VAULT_KEY": "rsf-repair-verifier-vault",
            "MESSAGE_UPLOAD_DIR": str(temp / "message_uploads"),
            "PROFILE_PICTURE_DIR": str(temp / "profile_pictures"),
            "CLIENT_ATTACHMENT_DIR": str(temp / "client_attachments"),
            "BACKUP_DIR": str(temp / "backups"),
            "TRUSTED_HOSTS": ["localhost", "127.0.0.1"],
        })
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        founder_name, founder_email, founder_password = "Repair Founder", "repair-founder@example.invalid", "repair-founder-pass"
        a_name, a_email, a_password = "Repair Partner A", "repair-a@example.invalid", "a"
        b_name, b_email, b_password = "Repair Partner B", "repair-b@example.invalid", "b"
        with test_app.app_context():
            db = get_db()
            duplicate_columns = {row["name"] for row in db.execute("PRAGMA table_info(duplicate_claims)").fetchall()}
            if "reasons" not in duplicate_columns:
                fail("Database schema check failed: duplicate lead review field is missing.")
            stage = db.execute("SELECT id,name,rate_bp FROM commission_stages ORDER BY sort_order LIMIT 1").fetchone()
            founder_id = db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'admin',1,0,?,?)""",
                (founder_name, founder_email, hash_password(founder_password), now, now),
            ).lastrowid
            a_user = db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'partner',1,0,?,?)""",
                (a_name, a_email, hash_password(a_password), now, now),
            ).lastrowid
            b_user = db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'partner',1,0,?,?)""",
                (b_name, b_email, hash_password(b_password), now, now),
            ).lastrowid
            a_partner = db.execute(
                "INSERT INTO partners(user_id,commission_stage_id,joined_at,active,historical_name) VALUES (?,?,?,1,?)",
                (a_user, stage["id"], now, "Repair Partner A"),
            ).lastrowid
            b_partner = db.execute(
                "INSERT INTO partners(user_id,commission_stage_id,joined_at,active,historical_name) VALUES (?,?,?,1,?)",
                (b_user, stage["id"], now, "Repair Partner B"),
            ).lastrowid
            lead_id = db.execute(
                """INSERT INTO leads(owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,website,website_domain,lead_source,summary_notes,status,lost_reason,demo_at,registered_at,last_activity_at,created_by_user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'NEW','',NULL,?,?,?)""",
                (a_partner, "Repair Client", "repair client", "Client", "client", "repair-client@example.invalid", "repair-client@example.invalid", "", "", "", "", "Verifier", "", now, now, founder_id),
            ).lastrowid
            followup_id = db.execute(
                """INSERT INTO followups(lead_id,owner_partner_id,title,due_at,notes,status,completed_at,created_by_user_id,created_at,updated_at)
                   VALUES (?,?,?,?,?,'OPEN',NULL,?,?,?)""",
                (lead_id, a_partner, "Call client", now, "", founder_id, now, now),
            ).lastrowid
            inquiry_id = db.execute(
                """INSERT INTO website_inquiries(created_at,updated_at,name,email,email_norm,company,message,status,claimed_by_partner_id,claimed_at,lead_id,source_type,source_slug,source_title,source_action)
                   VALUES (?,?,?,?,?,?,?,'CLAIMED',?,?,?,?,?,?,?)""",
                (now, now, "Client", "repair-client@example.invalid", "repair-client@example.invalid", "Repair Client", "Hello", a_partner, now, lead_id, "website", "contact", "Contact", "submit"),
            ).lastrowid
            conversation_id = db.execute(
                """INSERT INTO client_conversations(inquiry_id,lead_id,owner_partner_id,client_name,client_email,company,subject,status,created_at,updated_at,first_response_due_at)
                   VALUES (?,?,?,?,?,?,?,'ACTIVE',?,?,?)""",
                (inquiry_id, lead_id, a_partner, "Client", "repair-client@example.invalid", "Repair Client", "Repair", now, now, now),
            ).lastrowid
            db.execute("UPDATE website_inquiries SET client_conversation_id=? WHERE id=?", (conversation_id, inquiry_id))
            db.execute(
                "INSERT INTO client_notifications(user_id,kind,entity_type,entity_id,title,body,created_at) VALUES (?,'CLIENT_MESSAGE','conversation',?,?,?,?)",
                (a_user, conversation_id, "Client message", "Needs reply", now),
            )
            claim_id = db.execute(
                """INSERT INTO duplicate_claims(attempted_by_partner_id,matched_lead_id,company_name,contact_name,email,phone,website,reasons,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,'OPEN',?)""",
                (b_partner, lead_id, "Repair Client", "Client", "repair-client@example.invalid", "", "", "email", now),
            ).lastrowid
            privacy_inquiry = db.execute(
                """INSERT INTO website_inquiries(created_at,updated_at,name,email,email_norm,company,message,status,source_type,source_slug,source_title,source_action)
                   VALUES (?,?,?,?,?,?,?,'UNCLAIMED','website','contact','Contact','submit')""",
                (now, now, "New Person", "repair-client@example.invalid", "repair-client@example.invalid", "Repair Client", "Check",),
            ).lastrowid
            db.commit()

        anonymous = test_app.test_client()
        contact = anonymous.get("/contact", follow_redirects=False)
        cache = contact.headers.get("Cache-Control", "")
        if contact.status_code != 200 or "no-store" not in cache or "private" not in cache:
            fail("Contact page privacy cache protection failed.")

        partner_client = test_app.test_client()
        if _login(partner_client, b_name, b_password).status_code != 302:
            fail("Repair verifier Partner login failed.")
        privacy_page = partner_client.get(f"/app/inquiries/{privacy_inquiry}", follow_redirects=False)
        privacy_html = privacy_page.get_data(as_text=True)
        if (privacy_page.status_code != 200
                or "Possible existing client" not in privacy_html
                or "Founder review is needed." not in privacy_html):
            fail("Partner duplicate warning is missing.")
        if "Repair Partner A" in privacy_html:
            fail("Partner duplicate warning leaked another Partner's identity.")
        profile = partner_client.get("/app/profile", follow_redirects=False)
        partner_csrf = _csrf_from(profile)
        if partner_client.post("/app/clients/sync-email", data={"csrf_token": partner_csrf}, follow_redirects=False).status_code != 403:
            fail("Sales Partner can trigger company-wide email sync.")

        founder_client = test_app.test_client()
        if _login(founder_client, founder_name, founder_password).status_code != 302:
            fail("Repair verifier Founder login failed.")
        duplicates = founder_client.get("/app/admin/duplicates", follow_redirects=False)
        result = founder_client.post(
            f"/app/admin/duplicates/{claim_id}/resolve",
            data={"csrf_token": _csrf_from(duplicates), "action": "reassign", "resolution_notes": "Move all active work"},
            follow_redirects=False,
        )
        if result.status_code != 302:
            fail("Duplicate-review reassignment failed.")
        with test_app.app_context():
            db = get_db()
            if db.execute("SELECT owner_partner_id FROM leads WHERE id=?", (lead_id,)).fetchone()["owner_partner_id"] != b_partner:
                fail("Duplicate-review reassignment did not move the Lead.")
            if db.execute("SELECT owner_partner_id FROM followups WHERE id=?", (followup_id,)).fetchone()["owner_partner_id"] != b_partner:
                fail("Duplicate-review reassignment did not move the open follow-up.")
            if db.execute("SELECT owner_partner_id FROM client_conversations WHERE id=?", (conversation_id,)).fetchone()["owner_partner_id"] != b_partner:
                fail("Duplicate-review reassignment did not move the client conversation.")
            if db.execute("SELECT claimed_by_partner_id FROM website_inquiries WHERE id=?", (inquiry_id,)).fetchone()["claimed_by_partner_id"] != b_partner:
                fail("Duplicate-review reassignment did not move the claimed inquiry.")
            old_notice = db.execute("SELECT read_at FROM client_notifications WHERE user_id=? AND entity_type='conversation' AND entity_id=? ORDER BY id LIMIT 1", (a_user, conversation_id)).fetchone()
            new_notice = db.execute("SELECT 1 FROM client_notifications WHERE user_id=? AND kind='CLIENT_REASSIGNED' AND entity_type='conversation' AND entity_id=?", (b_user, conversation_id)).fetchone()
            if not old_notice or not old_notice["read_at"] or not new_notice:
                fail("Reassignment notification ownership was not updated safely.")

            db.execute("UPDATE leads SET status='WON' WHERE id=?", (lead_id,))
            sale_id = db.execute(
                """INSERT INTO sales(lead_id,partner_id,client_name,product_service,deal_amount_cents,invoiced_cents,collected_cents,qualifying_revenue_cents,payment_status,sale_date,notes,created_by_user_id,created_at,updated_at)
                   VALUES (?,?,?,?,10000,10000,10000,10000,'PAID',?,'',?,?,?)""",
                (lead_id, b_partner, "Repair Client", "Repair Service", now[:10], founder_id, now, now),
            ).lastrowid
            commission_id = db.execute(
                """INSERT INTO commissions(sale_id,partner_id,stage_name_snapshot,rate_bp_snapshot,qualifying_revenue_cents,adjustment_cents,commission_amount_cents,status,approval_date,paid_date,notes,created_at,updated_at)
                   VALUES (?,?,?,?,10000,0,4000,'PAID',?,?, '',?,?)""",
                (sale_id, b_partner, stage["name"], stage["rate_bp"], now, now, now, now),
            ).lastrowid
            db.commit()

        sale_page = founder_client.get(f"/app/sales/{sale_id}", follow_redirects=False)
        correction = founder_client.post(
            f"/app/sales/{sale_id}/corrections",
            data={
                "csrf_token": _csrf_from(sale_page),
                "kind": "REFUND",
                "deal_amount": "100.00",
                "amount_invoiced": "100.00",
                "amount_collected": "80.00",
                "qualifying_revenue": "80.00",
                "payment_status": "REFUNDED_ADJUSTED",
                "note": "Customer refund",
                "commission_change": "0.00",
            },
            follow_redirects=False,
        )
        if correction.status_code != 302:
            fail("Paid commission correction could not be recorded.")
        with test_app.app_context():
            db = get_db()
            original = db.execute("SELECT commission_amount_cents,status FROM commissions WHERE id=?", (commission_id,)).fetchone()
            saved = db.execute("SELECT * FROM sale_corrections WHERE commission_id=?", (commission_id,)).fetchone()
            current_sale = db.execute("SELECT deal_amount_cents,invoiced_cents,collected_cents,qualifying_revenue_cents,payment_status FROM sales WHERE id=?", (sale_id,)).fetchone()
            if not original or original["commission_amount_cents"] != 4000 or original["status"] != "PAID":
                fail("Paid commission history was rewritten by a correction.")
            if not saved or saved["commission_change_cents"] != -800:
                fail("Commission correction history was not calculated or saved correctly.")
            if current_sale["deal_amount_cents"] != 10000 or current_sale["invoiced_cents"] != 10000 or current_sale["collected_cents"] != 8000 or current_sale["qualifying_revenue_cents"] != 8000 or current_sale["payment_status"] != "REFUNDED_ADJUSTED":
                fail("Sale correction did not update the current financial state.")

def verify_public_source_baseline() -> None:
    manifest_path = ROOT / "scripts" / "PUBLIC_SOURCE_BASELINE.json"
    if not manifest_path.exists():
        fail("Public website baseline file is missing.")
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = []
    for rel, wanted in expected.items():
        path = ROOT / rel
        if not path.is_file():
            changed.append(rel + " (missing)")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != wanted:
            changed.append(rel)
    if changed:
        fail("Public website source changed unexpectedly: " + ", ".join(changed[:8]))




def verify_deployment_workflow() -> None:
    combined = ROOT / "installers" / "SETUP_AND_DEPLOY_RSF_MAIN_SYSTEM.bat"
    deploy_bat = ROOT / "deployment" / "DEPLOY_RSF_LIVE.bat"
    publish_bat = ROOT / "deployment" / "PUBLISH_RSF_ONLINE.bat"
    deploy = ROOT / "scripts" / "deploy_render_unified.py"
    if not combined.is_file() or not deploy_bat.is_file() or not publish_bat.is_file() or not deploy.is_file():
        fail("Local + live deployment workflow is missing.")
    bat = combined.read_text(encoding="utf-8", errors="replace")
    deploy_bat_text = deploy_bat.read_text(encoding="utf-8", errors="replace")
    publish_bat_text = publish_bat.read_text(encoding="utf-8", errors="replace")
    deploy_text = deploy.read_text(encoding="utf-8", errors="replace")
    required_bat = (
        "SETUP_RSF_MAIN_SYSTEM.bat",
        "DEPLOY_RSF_LIVE.bat",
        "LOCAL VERIFIED OK",
        "LIVE VERIFIED OK",
    )
    if any(marker not in bat for marker in required_bat):
        fail("Local + live CMD workflow is incomplete.")
    # Windows paths contain spaces. The Python executable must always be quoted.
    quoted_python_marker = '"%LOCAL_PYTHON%"'
    if quoted_python_marker not in deploy_bat_text or quoted_python_marker not in publish_bat_text:
        fail("Live deployment launcher check failed: Python path is not safely quoted.")
    required_deploy = (
        "PUBLIC_PROTECTED",
        "PRIVATE_FILES",
        "git", "clone",
        "public_hashes",
        "Live Partner Workspace is still using the old email login.",
        "LIVE VERIFIED OK",
        "/system/health",
    )
    if any(marker not in deploy_text for marker in required_deploy):
        fail("Safe live deployment verification is incomplete.")

def main() -> None:
    verify_project_layout()
    verify_public_source_baseline()
    verify_deployment_workflow()
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
    setup_deploy_path = ROOT / "installers" / "SETUP_AND_DEPLOY_RSF_MAIN_SYSTEM.bat"
    deploy_bat_path = ROOT / "deployment" / "DEPLOY_RSF_LIVE.bat"
    publish_bat_path = ROOT / "deployment" / "PUBLISH_RSF_ONLINE.bat"
    launcher_vbs_path = ROOT / "installers" / "launchers" / "RSF Partner System Launcher.vbs"
    launcher_py_path = ROOT / "scripts" / "LAUNCH_RSF_PARTNER_SYSTEM.py"
    installer_py_path = ROOT / "scripts" / "INSTALL_RSF_PARTNER_SYSTEM.py"
    setup_text = setup_path.read_text(encoding="utf-8", errors="replace") if setup_path.exists() else ""
    setup_deploy_text = setup_deploy_path.read_text(encoding="utf-8", errors="replace") if setup_deploy_path.exists() else ""
    deploy_bat_text = deploy_bat_path.read_text(encoding="utf-8", errors="replace") if deploy_bat_path.exists() else ""
    publish_bat_text = publish_bat_path.read_text(encoding="utf-8", errors="replace") if publish_bat_path.exists() else ""
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
    if "%TEMP%\\rsf_python_path.txt" in setup_text or "rsf_python_path.txt" in setup_text:
        fail("Active setup must not depend on a temporary Python-path launcher file.")

    # Windows CMD must never split `RSF Main System` at the spaces. The active
    # one-command chain therefore resolves the release root once, calls child BATs
    # by relative quoted names, and passes Python script paths as quoted arguments.
    required_setup_deploy_markers = (
        'set "RSF_RELEASE_ROOT=',
        'pushd "%RSF_RELEASE_ROOT%"',
        'call "installers\\SETUP_RSF_MAIN_SYSTEM.bat"',
        'call "deployment\\DEPLOY_RSF_LIVE.bat"',
        'LOCAL VERIFIED OK',
        'LIVE VERIFIED OK',
        'pause',
    )
    if any(marker not in setup_deploy_text for marker in required_setup_deploy_markers):
        fail("One-command local + live deployment launcher is not path-safe or does not preserve final verification output.")
    for bat_name, bat_text, script_var in (
        ("DEPLOY_RSF_LIVE.bat", deploy_bat_text, "DEPLOY_SCRIPT"),
        ("PUBLISH_RSF_ONLINE.bat", publish_bat_text, "PUBLISH_SCRIPT"),
    ):
        required = (
            'set "RSF_RELEASE_ROOT=',
            'pushd "%RSF_RELEASE_ROOT%"',
            f'py.exe -3 "%{script_var}%"',
            f'python.exe "%{script_var}%"',
            f'"%LOCAL_PYTHON%" "%{script_var}%"',
        )
        if any(marker not in bat_text for marker in required):
            fail(f"{bat_name} path-with-spaces handling is incomplete.")
    deploy_source = (ROOT / "scripts" / "deploy_render_unified.py").read_text(encoding="utf-8", errors="replace")
    if "shell=True" in deploy_source or 'shell = True' in deploy_source:
        fail("Python deployment launcher must use argument lists, not shell=True command strings.")
    if 'GITHUB VERIFIED OK' not in deploy_source or 'git", "ls-remote"' not in deploy_source:
        fail("Deployment workflow does not verify that GitHub main actually reached the exact release commit.")
    if "\\n.message-image" in css_text or "\\n\\n/* v1.1.16" in css_text:
        fail("Messages image viewer check failed: escaped newlines are corrupting viewer CSS.")

    profile_template = (ROOT / "app" / "templates" / "profile.html").read_text(encoding="utf-8", errors="replace")
    base_template = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8", errors="replace")
    account_security_template = (ROOT / "app" / "templates" / "account_security.html").read_text(encoding="utf-8", errors="replace")
    login_template = (ROOT / "app" / "templates" / "login.html").read_text(encoding="utf-8", errors="replace")
    partner_form_template = (ROOT / "app" / "templates" / "partner_form.html").read_text(encoding="utf-8", errors="replace")
    partners_list_template = (ROOT / "app" / "templates" / "partners_list.html").read_text(encoding="utf-8", errors="replace")
    if 'name="name"' not in login_template or 'name="password"' not in login_template or 'name="email"' in login_template:
        fail("Private workspace login is not Name + Password only.")
    if 'name="email"' in partner_form_template or '>Email<' in partners_list_template:
        fail("User-account email is still visible in Partner account screens.")
    partner_detail_template = (ROOT / "app" / "templates" / "partner_detail.html").read_text(encoding="utf-8", errors="replace")
    routes_text = (ROOT / "app" / "routes.py").read_text(encoding="utf-8", errors="replace")
    centralized_account_source = account_security_template + profile_template + partner_detail_template + base_template + routes_text + js_text + css_text
    credential_vault_source = (ROOT / "app" / "credential_vault.py").read_text(encoding="utf-8", errors="replace")
    required_account_security = (
        "Account &amp; Security", "Founder Account", "Partner Accounts", "Current Password",
        "security-change-disclosure", "partner-security-list", "Delete Partner",
        "/admin/settings/account-security", "founder_password_change", "confirm_partner_password",
        "data-account-disclosure", "data-toggle-password", "data-vault-reveal", "data-vault-copy",
        "account_security_reveal_password", "v1.9.4 — Founder-only current password visibility",
    )
    if any(marker not in (centralized_account_source + credential_vault_source) for marker in required_account_security):
        fail("Founder password visibility / simplified security workspace is incomplete.")
    for forbidden in ("Founder/Admin", "Founder / Admin", "Employee", "Staff", "Deactivate", "Suspend", "Archive"):
        if forbidden.lower() in account_security_template.lower():
            fail(f"Account & Security contains obsolete role/lifecycle terminology: {forbidden}")
    if 'name="current_password"' in profile_template or 'minlength="12"' in profile_template or "12+ characters" in profile_template:
        fail("Founder password controls/rules are still scattered on Profile.")
    required_vault_crypto = ("Fernet", "encrypt_password", "decrypt_password", "account_password_vault", "CREDENTIAL_VAULT_KEY")
    vault_source = credential_vault_source + (ROOT / "app" / "db.py").read_text(encoding="utf-8", errors="replace") + (ROOT / "config.py").read_text(encoding="utf-8", errors="replace")
    if any(marker not in vault_source for marker in required_vault_crypto):
        fail("Founder password visibility is not backed by the encrypted credential vault.")
    if "Change password" in partner_detail_template or "Delete Partner Permanently" in partner_detail_template:
        fail("Partner credential controls are still scattered on Partner detail.")
    required_profile_picture = (
        'enctype="multipart/form-data"', 'name="profile_picture"', 'value="avatar"', 'value="avatar_remove"',
        'profile-picture-manager', '@bp.get("/profile-picture/<int:user_id>")', 'PROFILE_PICTURE_MAX_BYTES',
        '_detect_profile_picture_type', 'data-call-avatar', 'currentCall.avatar_url',
    )
    combined_profile_source = profile_template + base_template + routes_text + js_text
    if any(marker not in combined_profile_source for marker in required_profile_picture):
        fail("Per-user profile-picture feature is incomplete.")

    ux_css = (ROOT / "app" / "static" / "css" / "workspace_v20.css").read_text(encoding="utf-8", errors="replace")
    required_organization = (
        'nav-section-label', '>Work<', '>Business<', 'sidebar-utility-links', 'Profile', 'Settings', 'Activity',
        'workspace-page-head', 'workspace-section', 'attention-strip', 'section-head', 'finance-brief',
        'topbar-context', 'pipeline-track', 'resource-row', 'history-disclosure',
    )
    organization_source = base_template + profile_template + ux_css
    if any(marker not in organization_source for marker in required_organization):
        fail("v1.11.0 simplified Workspace information architecture is incomplete.")

    admin_dashboard_template = (ROOT / "app" / "templates" / "dashboard_admin.html").read_text(encoding="utf-8", errors="replace")
    partner_dashboard_template = (ROOT / "app" / "templates" / "dashboard_partner.html").read_text(encoding="utf-8", errors="replace")
    leads_template = (ROOT / "app" / "templates" / "leads_list.html").read_text(encoding="utf-8", errors="replace")
    lead_detail_template = (ROOT / "app" / "templates" / "lead_detail.html").read_text(encoding="utf-8", errors="replace")
    inquiries_template = (ROOT / "app" / "templates" / "inquiries.html").read_text(encoding="utf-8", errors="replace")
    workspace_refinement_source = (
        admin_dashboard_template + partner_dashboard_template + leads_template + lead_detail_template +
        inquiries_template + base_template + routes_text + js_text + css_text
    )
    workspace_refinement_source += (ROOT / "app" / "static" / "css" / "workspace_v20.css").read_text(encoding="utf-8", errors="replace")
    required_workspace_refinement = (
        'metrics.awaiting_response', 'metrics.contacted', 'metrics.proposal', 'attention-strip', 'pipeline-track',
        'operational-table', 'streamlined-inbox-columns', 'data-lead-status-form', 'data-status-field', 'syncStatusFields',
        'linked-record-row', 'partner-security-list', 'sidebar-utility-links',
    )
    if any(marker not in workspace_refinement_source for marker in required_workspace_refinement):
        fail("v1.11.0 Workspace simplification/refinement is incomplete.")

    app = create_app()
    with app.app_context():
        db = get_db()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            fail(f"Database integrity check failed: {integrity}")

        admin = db.execute("SELECT * FROM users WHERE role='admin' AND active=1 ORDER BY id LIMIT 1").fetchone()
        if not admin:
            fail("No active Founder account was found.")
        active_accounts = db.execute(
            """SELECT u.id,u.full_name,u.role,v.encrypted_password
               FROM users u LEFT JOIN account_password_vault v ON v.user_id=u.id
               LEFT JOIN partners p ON p.user_id=u.id
               WHERE u.active=1 AND (u.role='admin' OR (u.role='partner' AND p.account_deleted_at IS NULL))
               ORDER BY u.id"""
        ).fetchall()
        for account in active_accounts:
            if not account["encrypted_password"]:
                fail(f"Password visibility data is missing for active account ID {account['id']}.")
            try:
                current_password = decrypt_password(account["encrypted_password"])
            except RuntimeError:
                fail(f"Password visibility data could not be read for active account ID {account['id']}.")
            matched = db.execute(
                "SELECT id,password_hash FROM users WHERE active=1 AND lower(trim(full_name))=lower(trim(?)) LIMIT 1",
                (account["full_name"],),
            ).fetchone()
            if not matched or int(matched["id"]) != int(account["id"]) or not check_password_hash(matched["password_hash"], current_password):
                fail(f"Existing account ID {account['id']} cannot be verified with Name + current Password.")

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
        if not {"delivery_status", "delivery_error"}.issubset(client_message_columns):
            fail("Unified client email delivery-state migration is incomplete.")
        migration = db.execute("SELECT name FROM schema_migrations WHERE version=13").fetchone()
        if not migration or "hard-partner-account-delete" not in migration["name"]:
            fail("Founder Partner-management database migration 13 is missing.")
        name_login_migration = db.execute("SELECT name FROM schema_migrations WHERE version=16").fetchone()
        if not name_login_migration or "name-password-login" not in name_login_migration["name"]:
            fail("Name + Password login migration 16 is missing.")
        duplicate_names = db.execute(
            """SELECT lower(trim(full_name)) login_name,COUNT(*) c FROM users WHERE active=1
               GROUP BY lower(trim(full_name)) HAVING COUNT(*)>1 LIMIT 1"""
        ).fetchone()
        if duplicate_names:
            fail("Active workspace accounts still have duplicate login Names.")
        if db.execute("SELECT 1 FROM users WHERE active=1 AND trim(COALESCE(full_name,''))='' LIMIT 1").fetchone():
            fail("An active workspace account has a blank login Name.")
        partner_info = {row["name"]: row for row in db.execute("PRAGMA table_info(partners)").fetchall()}
        if "historical_name" not in partner_info or "account_deleted_at" not in partner_info:
            fail("Partner historical-attribution fields are missing.")
        if int(partner_info["user_id"]["notnull"] or 0) != 0:
            fail("Partner account deletion migration is incomplete: partners.user_id is still required.")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            fail("Installed database has foreign-key violations.")

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
        founder_dashboard_markers = ("Dashboard", "Partner work", "Next follow-ups", "Pipeline", "Money overview")
        founder_dashboard_missing = [marker for marker in founder_dashboard_markers if marker not in dashboard_html]
        if dashboard_page.status_code != 200 or founder_dashboard_missing:
            fail(
                "Founder dashboard check failed. "
                f"Status={dashboard_page.status_code}; missing={founder_dashboard_missing or 'none'}."
            )

        founder_profile = admin_client.get("/app/profile", follow_redirects=False)
        founder_profile_html = founder_profile.get_data(as_text=True)
        if founder_profile.status_code != 200 or "Founder" not in founder_profile_html or "Founder / Admin" in founder_profile_html or "profile-picture-manager" not in founder_profile_html or 'name="profile_picture"' not in founder_profile_html:
            fail("Founder profile-picture self-service check failed.")
        if "profile-picture-manager" not in founder_profile_html or "Photo" not in founder_profile_html or "Details" not in founder_profile_html:
            fail("Founder focused profile check failed.")

        messages_page = admin_client.get("/app/messages", follow_redirects=False)
        if messages_page.status_code != 200 or "Messages" not in messages_page.get_data(as_text=True):
            fail("Founder messaging check failed.")

        client_inbox_page = admin_client.get("/app/inquiries", follow_redirects=False)
        inbox_html = client_inbox_page.get_data(as_text=True)
        if client_inbox_page.status_code != 200 or "Client Inbox" not in inbox_html or "New inquiries" not in inbox_html:
            fail("Unified client inbox check failed.")
        inbox_template = (ROOT / "app" / "templates" / "inquiries.html").read_text(encoding="utf-8", errors="replace")
        if "Needs reply" not in inbox_template or "first reply" not in inbox_template.lower():
            fail("Unified client response-accountability UI check failed.")
        if "data-client-unread" not in base_template or "setClientUnread" not in js_text:
            fail("Unified client notification check failed.")
        client_template = (ROOT / "app" / "templates" / "client_conversation.html").read_text(encoding="utf-8", errors="replace")
        if 'name="attachments"' not in client_template or "delivery-status" not in client_template or "Sync Email" not in client_template:
            fail("Unified client email/attachment workspace check failed.")

        partner = db.execute(
            """SELECT u.*,p.id partner_id,p.active AS partner_active,cs.name stage_name,cs.rate_bp
               FROM users u JOIN partners p ON p.user_id=u.id
               JOIN commission_stages cs ON cs.id=p.commission_stage_id
               WHERE u.role='partner' AND u.active=1 AND p.active=1 ORDER BY p.id LIMIT 1"""
        ).fetchone()

        if partner:
            client = app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = partner["id"]
                session["credential"] = session_credential(partner)
                session.permanent = True

            if client.get("/app/admin/partners", follow_redirects=False).status_code != 403:
                fail("Partner privacy check failed: Founder-only page was not blocked.")
            if client.get("/app/admin/settings/account-security", follow_redirects=False).status_code != 403:
                fail("Partner privacy check failed: Account & Security was not blocked.")

            partner_dashboard = client.get("/app/", follow_redirects=False)
            partner_dashboard_html = partner_dashboard.get_data(as_text=True)
            partner_dashboard_markers = ("Dashboard", "Next work", "Pipeline", "Commissions", "Client replies")
            partner_dashboard_missing = [marker for marker in partner_dashboard_markers if marker not in partner_dashboard_html]
            if partner_dashboard.status_code != 200 or partner_dashboard_missing:
                fail(
                    "Partner dashboard check failed. "
                    f"Status={partner_dashboard.status_code}; missing={partner_dashboard_missing or 'none'}."
                )

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
            if "profile-picture-manager" not in profile_text or 'name="profile_picture"' not in profile_text or '>Upload</button>' not in profile_text:
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

    verify_partner_account_management()
    verify_controlled_repair_regressions()

    print("Installed system verified: database OK, Name + Password login OK, Founder Name login OK, simplified Account & Security OK, exact Founder password change OK, Founder persistent encrypted password show/hide/copy OK, old Founder password/session invalidation OK, Founder-only Partner management OK, Partner create/view/edit OK, exact Founder-chosen Partner passwords OK, Partner password reset/session invalidation OK, Founder persistent Partner password reveal/copy OK, Partner self-service password change blocked OK, forged Founder actions blocked OK, cross-Partner privacy OK, Partner active-work delete protection OK, active work transfer OK, permanent Partner authentication removal OK, deleted Partner login blocked OK, historical sale/commission/message/client records preserved OK, v1.11.2 repair regressions OK, database integrity/foreign keys OK, CSRF OK, trusted hosts OK, session security OK, security headers OK, RSF Emerald + Champagne simplified Workspace UI OK, desktop launchers OK, unified public website OK, Partner Workspace OK, safe local-to-live deployment workflow OK.")


if __name__ == "__main__":
    main()
