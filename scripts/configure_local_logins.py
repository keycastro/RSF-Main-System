"""Optionally configure local Founder and preview Partner credentials during setup.

Passwords are read only from process environment variables. They are never written
into the release source code or .env file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.auth import hash_password, valid_password
from app.db import ensure_database, get_db
from app.services import utcnow_iso


def required_password(name: str) -> str | None:
    value = os.environ.get(name)
    if not value:
        return None
    if not valid_password(value):
        raise SystemExit(f"{name} must not be empty.")
    return value


def main() -> None:
    admin_password = required_password("RSF_SETUP_ADMIN_PASSWORD")
    partner_password = required_password("RSF_SETUP_PARTNER_PASSWORD")
    admin_email = os.environ.get("RSF_SETUP_ADMIN_EMAIL", "founder@rsf.local").strip().lower()
    partner_email = os.environ.get("RSF_SETUP_PARTNER_EMAIL", "partner@rsf.local").strip().lower()
    partner_name = os.environ.get("RSF_SETUP_PARTNER_NAME", "RSF Test Partner").strip() or "RSF Test Partner"

    if not admin_password and not partner_password:
        print("Local login configuration skipped: no setup passwords were provided.")
        return

    app = create_app()
    with app.app_context():
        ensure_database()
        db = get_db()
        now = utcnow_iso()

        admin = db.execute("SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        if admin_password:
            conflict = db.execute("SELECT id,role FROM users WHERE lower(email)=? AND id<>?", (admin_email, admin["id"] if admin else -1)).fetchone()
            if conflict:
                raise SystemExit(f"Cannot set Founder email to {admin_email}: another account already uses it.")
            if admin:
                db.execute(
                    """UPDATE users SET email=?,password_hash=?,active=1,force_password_change=0,
                       failed_login_count=0,locked_until=NULL,updated_at=? WHERE id=?""",
                    (admin_email, hash_password(admin_password), now, admin["id"]),
                )
                admin_id = admin["id"]
            else:
                cur = db.execute(
                    """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                       VALUES (?,?,?,'admin',1,0,?,?)""",
                    ("Key Ando Castro", admin_email, hash_password(admin_password), now, now),
                )
                admin_id = cur.lastrowid
            db.execute(
                """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (admin_id, "LOCAL_FOUNDER_LOGIN_CONFIGURED", "user", admin_id,
                 "Founder local login was configured during setup.", "{}", now),
            )
            first_access = ROOT / "FIRST_RUN_FOUNDER_ACCESS.txt"
            if first_access.exists():
                try:
                    first_access.unlink()
                except OSError:
                    pass

        if partner_password:
            stage = db.execute("SELECT * FROM commission_stages WHERE code='FOUNDING_1' AND active=1").fetchone()
            if not stage:
                raise SystemExit("Founding Partner #1 commission stage is missing.")

            existing = db.execute("SELECT * FROM users WHERE lower(email)=?", (partner_email,)).fetchone()
            if existing and existing["role"] != "partner":
                raise SystemExit(f"Cannot create preview partner: {partner_email} belongs to a non-partner account.")

            if existing:
                partner_user_id = existing["id"]
                db.execute(
                    """UPDATE users SET full_name=?,password_hash=?,active=1,force_password_change=0,
                       failed_login_count=0,locked_until=NULL,updated_at=? WHERE id=?""",
                    (partner_name[:160], hash_password(partner_password), now, partner_user_id),
                )
            else:
                cur = db.execute(
                    """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                       VALUES (?,?,?,'partner',1,0,?,?)""",
                    (partner_name[:160], partner_email, hash_password(partner_password), now, now),
                )
                partner_user_id = cur.lastrowid

            partner = db.execute("SELECT * FROM partners WHERE user_id=?", (partner_user_id,)).fetchone()
            if partner:
                db.execute(
                    "UPDATE partners SET full_name_snapshot=?,email_snapshot=?,commission_stage_id=?,active=1 WHERE id=?",
                    (partner_name[:160], partner_email, stage["id"], partner["id"]),
                )
                partner_id = partner["id"]
            else:
                cur = db.execute(
                    """INSERT INTO partners(user_id,full_name_snapshot,email_snapshot,commission_stage_id,phone,notes,joined_at,active)
                       VALUES (?,?,?,?,?,'Local preview account created for Founder testing.',?,1)""",
                    (partner_user_id, partner_name[:160], partner_email, stage["id"], "", now),
                )
                partner_id = cur.lastrowid

            actor = db.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            db.execute(
                """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (actor["id"] if actor else None, "LOCAL_PREVIEW_PARTNER_CONFIGURED", "partner", partner_id,
                 "Local preview Partner account configured at the Founding Partner #1 rate.",
                 '{"stage":"Founding Partner #1","rate_bp":4000}', now),
            )

        db.commit()

        if admin_password:
            row = db.execute("SELECT email,force_password_change,active FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            assert row and row["email"].lower() == admin_email and row["active"] == 1 and row["force_password_change"] == 0
        if partner_password:
            row = db.execute(
                """SELECT u.email,u.force_password_change,u.active,p.active partner_active,cs.code,cs.rate_bp
                   FROM users u JOIN partners p ON p.user_id=u.id
                   JOIN commission_stages cs ON cs.id=p.commission_stage_id
                   WHERE lower(u.email)=?""",
                (partner_email,),
            ).fetchone()
            assert row and row["active"] == 1 and row["partner_active"] == 1
            assert row["force_password_change"] == 0 and row["code"] == "FOUNDING_1" and row["rate_bp"] == 4000

    print("Requested local Founder and Partner logins configured successfully. No business records were deleted.")


if __name__ == "__main__":
    main()
