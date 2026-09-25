from __future__ import annotations

import os
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import get_db, close_db, using_postgres, OperationalError
from .client_ops import email_receive_configured, sync_inbound_email

_started = False
_started_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _lease(name: str, holder: str, seconds: int) -> bool:
    db = get_db()
    now = _now()
    until = now + timedelta(seconds=seconds)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT holder,lease_until FROM background_leases WHERE name=?", (name,)).fetchone()
        if row:
            try:
                current_until = datetime.fromisoformat(row["lease_until"])
            except Exception:
                current_until = now - timedelta(seconds=1)
            if current_until > now and row["holder"] != holder:
                db.rollback()
                return False
            db.execute(
                "UPDATE background_leases SET holder=?,lease_until=?,updated_at=? WHERE name=?",
                (holder, _iso(until), _iso(now), name),
            )
        else:
            db.execute(
                "INSERT INTO background_leases(name,holder,lease_until,updated_at) VALUES (?,?,?,?)",
                (name, holder, _iso(until), _iso(now)),
            )
        db.commit()
        return True
    except (sqlite3.OperationalError, OperationalError):
        try:
            db.rollback()
        except Exception:
            pass
        return False


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(source)) as original, sqlite3.connect(str(destination)) as backup:
        original.backup(backup)
        result = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError("Backup integrity check failed.")


def _add_tree(zf: zipfile.ZipFile, folder: Path, prefix: str) -> None:
    if not folder.exists():
        return
    for path in folder.rglob("*"):
        if path.is_file():
            zf.write(path, f"{prefix}/{path.relative_to(folder).as_posix()}")


def create_backup(app) -> Path | None:
    if app.config.get("DATABASE_URL"):
        return None
    database = Path(app.config["DATABASE"])
    if not database.exists():
        return None
    backup_dir = Path(app.config["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    temp_db = backup_dir / f".rsf-{stamp}.db"
    output = backup_dir / f"RSF_BACKUP_{stamp}.zip"
    _backup_database(database, temp_db)
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(temp_db, "database/rsf_sales_partner.db")
            for key, prefix in [
                ("MESSAGE_UPLOAD_DIR", "message_uploads"),
                ("PROFILE_PICTURE_DIR", "profile_pictures"),
                ("CLIENT_ATTACHMENT_DIR", "client_attachments"),
            ]:
                _add_tree(zf, Path(app.config[key]), prefix)
            env_path = Path(app.root_path).parent / ".env"
            # Do not put secrets in automatic backups. Preserve only a marker file.
            zf.writestr("README.txt", "RSF protected data backup. Email/server secrets are intentionally not included.\n")
    finally:
        temp_db.unlink(missing_ok=True)

    # Keep the latest 14 automatic snapshots in this destination.
    backups = sorted(backup_dir.glob("RSF_BACKUP_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[14:]:
        try:
            old.unlink()
        except OSError:
            pass
    return output



def _emit_overdue_notifications() -> None:
    db = get_db()
    now = _iso(_now())
    rows = db.execute(
        """SELECT c.id,c.owner_partner_id,c.company,c.client_name,p.user_id AS partner_user_id
           FROM client_conversations c
           LEFT JOIN partners p ON p.id=c.owner_partner_id
           WHERE c.status='ACTIVE' AND c.owner_partner_id IS NOT NULL
             AND c.first_responded_at IS NULL AND c.first_response_due_at IS NOT NULL
             AND c.first_response_due_at < ?""", (now,)
    ).fetchall()
    founders = [int(r["id"]) for r in db.execute("SELECT id FROM users WHERE role='admin' AND active=1").fetchall()]
    for row in rows:
        recipients = [int(row["partner_user_id"])] if row["partner_user_id"] else []
        recipients.extend(founders)
        label = row["company"] or row["client_name"]
        for user_id in set(recipients):
            exists = db.execute(
                """SELECT 1 FROM client_notifications
                   WHERE user_id=? AND kind='RESPONSE_OVERDUE' AND entity_type='conversation' AND entity_id=? LIMIT 1""",
                (user_id, row["id"]),
            ).fetchone()
            if not exists:
                db.execute(
                    """INSERT INTO client_notifications(user_id,kind,entity_type,entity_id,title,body,created_at)
                       VALUES (?,'RESPONSE_OVERDUE','conversation',?,?,?,?)""",
                    (user_id, row["id"], f"First response overdue: {label}", "This claimed client has not received a first RSF reply yet.", now),
                )
    db.commit()

def _worker(app) -> None:
    holder = f"{os.getpid()}-{uuid.uuid4().hex}"
    email_interval = int(app.config.get("EMAIL_SYNC_INTERVAL_SECONDS", 60))
    backup_interval = int(app.config.get("AUTO_BACKUP_INTERVAL_HOURS", 24)) * 3600
    next_backup = 0.0
    while True:
        try:
            with app.app_context():
                _emit_overdue_notifications()
                if app.config.get("AUTO_EMAIL_SYNC") and email_receive_configured():
                    if _lease("email-sync", holder, max(email_interval * 2, 90)):
                        try:
                            sync_inbound_email(limit=100)
                        except Exception:
                            app.logger.exception("Automatic RSF client email sync failed")
                        finally:
                            close_db()
                if time.time() >= next_backup:
                    if _lease("automatic-backup", holder, 300):
                        try:
                            create_backup(app)
                        except Exception:
                            app.logger.exception("Automatic RSF backup failed")
                        finally:
                            close_db()
                    next_backup = time.time() + backup_interval
        except Exception:
            app.logger.exception("RSF background worker cycle failed")
        time.sleep(max(30, min(email_interval, 120)))


def start_background_services(app) -> None:
    global _started
    with _started_lock:
        if _started:
            return
        _started = True
        thread = threading.Thread(target=_worker, args=(app,), name="rsf-background", daemon=True)
        thread.start()
