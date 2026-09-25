from __future__ import annotations

import json
import sqlite3
from io import BytesIO
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from .auth import (
    admin_required,
    authenticate,
    csrf_token,
    hash_password,
    login_required,
    login_user,
    safe_next,
    valid_email,
    valid_password,
    validate_csrf,
)
from .db import get_db, IntegrityError, using_postgres
from .services import (
    PARTNER_ALLOWED_STATUSES,
    PAYMENT_STATUSES,
    PIPELINE,
    RESOURCE_CATEGORIES,
    commission_amount,
    create_commission_for_sale,
    duplicate_candidates,
    log_activity,
    money_to_cents,
    normalize_date,
    normalize_domain,
    normalize_email,
    normalize_local_datetime,
    normalize_phone,
    normalize_text,
    signed_money_to_cents,
    setting,
    sync_pending_commission,
    touch_lead,
    utcnow_iso,
)

bp = Blueprint("main", __name__)


def local_now_input() -> str:
    return datetime.now().astimezone().replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def today_str() -> str:
    return date.today().isoformat()


def partner_scope_id() -> int | None:
    return g.partner["id"] if g.user and g.user["role"] == "partner" and g.partner else None




def authorized_conversation_partner(partner_id: int):
    db = get_db()
    partner = db.execute(
        """SELECT p.*, u.full_name, u.email, u.role AS user_role, u.avatar_stored_name, u.active AS user_active
           FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.id=?""",
        (partner_id,),
    ).fetchone()
    if not partner:
        abort(404)
    if g.user["role"] == "partner" and (not g.partner or g.partner["id"] != partner_id):
        # Hide other partners completely instead of revealing that a thread exists.
        abort(404)
    return partner


def message_unread_count() -> int:
    if not g.user:
        return 0
    db = get_db()
    if g.user["role"] == "admin":
        return db.execute(
            """SELECT COUNT(*) c FROM messages m
               JOIN partners p ON p.id=m.partner_id
               WHERE m.sender_user_id=p.user_id AND m.founder_read_at IS NULL"""
        ).fetchone()["c"]
    return db.execute(
        """SELECT COUNT(*) c FROM messages
           WHERE partner_id=? AND sender_user_id<>? AND partner_read_at IS NULL""",
        (g.partner["id"], g.user["id"]),
    ).fetchone()["c"]


def client_unread_count() -> int:
    if not g.user:
        return 0
    return get_db().execute(
        "SELECT COUNT(*) c FROM client_notifications WHERE user_id=? AND read_at IS NULL",
        (g.user["id"],),
    ).fetchone()["c"]


def mark_client_notifications_read(*, entity_type: str | None = None, entity_id: int | None = None) -> None:
    if not g.user:
        return
    db = get_db()
    now = utcnow_iso()
    if entity_type and entity_id is not None:
        db.execute(
            """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
               WHERE user_id=? AND entity_type=? AND entity_id=?""",
            (now, g.user["id"], entity_type, entity_id),
        )
    else:
        db.execute(
            "UPDATE client_notifications SET read_at=COALESCE(read_at,?) WHERE user_id=?",
            (now, g.user["id"]),
        )
    db.commit()


def client_overdue_count() -> int:
    if not g.user:
        return 0
    db = get_db()
    params: list = [utcnow_iso()]
    sql = """SELECT COUNT(*) c FROM client_conversations c
             WHERE c.status='ACTIVE' AND c.owner_partner_id IS NOT NULL
               AND c.first_responded_at IS NULL AND c.first_response_due_at IS NOT NULL
               AND c.first_response_due_at < ?"""
    if g.user["role"] == "partner":
        sql += " AND c.owner_partner_id=?"
        params.append(g.partner["id"])
    return db.execute(sql, params).fetchone()["c"]


def mark_conversation_read(partner) -> None:
    db = get_db()
    now = utcnow_iso()
    if g.user["role"] == "admin":
        db.execute(
            """UPDATE messages SET founder_read_at=COALESCE(founder_read_at, ?)
               WHERE partner_id=? AND sender_user_id=? AND founder_read_at IS NULL""",
            (now, partner["id"], partner["user_id"]),
        )
    else:
        db.execute(
            """UPDATE messages SET partner_read_at=COALESCE(partner_read_at, ?)
               WHERE partner_id=? AND sender_user_id<>? AND partner_read_at IS NULL""",
            (now, partner["id"], g.user["id"]),
        )


MESSAGE_MAX_ATTACHMENTS = 5
MESSAGE_MAX_FILE_BYTES = 15 * 1024 * 1024
MESSAGE_MAX_TOTAL_BYTES = 25 * 1024 * 1024
MESSAGE_FILE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
}


def _message_upload_dir() -> Path:
    path = Path(current_app.config["MESSAGE_UPLOAD_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


PROFILE_PICTURE_MAX_BYTES = 8 * 1024 * 1024
PROFILE_PICTURE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _profile_picture_dir() -> Path:
    path = Path(current_app.config["PROFILE_PICTURE_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _detect_profile_picture_type(header: bytes) -> tuple[str, str] | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def _profile_picture_info(storage) -> dict:
    if storage is None:
        raise ValueError("Choose an image first.")
    original = secure_filename(storage.filename or "")
    if not original:
        raise ValueError("Choose an image first.")
    suffix = Path(original).suffix.lower()
    if suffix not in PROFILE_PICTURE_TYPES:
        raise ValueError("Use a JPG, PNG, or WEBP image.")
    try:
        storage.stream.seek(0, 2)
        size = int(storage.stream.tell())
        storage.stream.seek(0)
        header = storage.stream.read(32)
        storage.stream.seek(0)
    except (AttributeError, OSError, ValueError):
        size = int(storage.content_length or 0)
        header = b""
    if size <= 0:
        raise ValueError("That image is empty.")
    if size > PROFILE_PICTURE_MAX_BYTES:
        raise ValueError("Profile pictures must be 8 MB or smaller.")
    detected = _detect_profile_picture_type(header)
    if not detected:
        raise ValueError("That file is not a valid JPG, PNG, or WEBP image.")
    actual_suffix, mime_type = detected
    expected_mime = PROFILE_PICTURE_TYPES[suffix]
    if expected_mime != mime_type and not (suffix == ".jpeg" and mime_type == "image/jpeg"):
        raise ValueError("The image file type does not match its extension.")
    return {
        "storage": storage,
        "mime_type": mime_type,
        "stored_name": f"{uuid4().hex}{actual_suffix}",
        "size_bytes": size,
    }


def _can_view_profile_picture(target_user) -> bool:
    if not g.user:
        return False
    if int(target_user["id"]) == int(g.user["id"]):
        return True
    if g.user["role"] == "admin":
        return True
    return target_user["role"] == "admin"


def _message_file_info(storage) -> dict:
    original = secure_filename(storage.filename or "")
    if not original:
        raise ValueError("Choose a file first.")
    suffix = Path(original).suffix.lower()
    mime = MESSAGE_FILE_TYPES.get(suffix)
    if not mime:
        raise ValueError("That file type is not supported.")
    try:
        storage.stream.seek(0, 2)
        size = int(storage.stream.tell())
        storage.stream.seek(0)
    except (AttributeError, OSError, ValueError):
        size = int(storage.content_length or 0)
    if size <= 0:
        raise ValueError("That file is empty.")
    if size > MESSAGE_MAX_FILE_BYTES:
        raise ValueError("Each file must be 15 MB or smaller.")
    return {
        "storage": storage,
        "original_name": original[:180],
        "suffix": suffix,
        "mime_type": mime,
        "size_bytes": size,
        "stored_name": f"{uuid4().hex}{suffix}",
    }


def _attachment_payload(row, partner_id: int) -> dict:
    base = url_for("main.message_attachment", partner_id=partner_id, attachment_id=row["id"])
    return {
        "id": row["id"],
        "name": row["original_name"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "is_image": str(row["mime_type"]).startswith("image/"),
        "url": base,
        "download_url": f"{base}?download=1",
    }


def _attachments_for_messages(db, partner_id: int, message_ids) -> dict[int, list[dict]]:
    ids = [int(value) for value in message_ids if value]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""SELECT * FROM message_attachments
             WHERE partner_id=? AND message_id IN ({placeholders})
             ORDER BY message_id,id""",
        [partner_id, *ids],
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for row in rows:
        result.setdefault(row["message_id"], []).append(_attachment_payload(row, partner_id))
    return result


def _founder_conversations(db, query: str = "") -> list[dict]:
    params = []
    where = ""
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        where = " WHERE (u.full_name LIKE ? ESCAPE '\\' OR u.email LIKE ? ESCAPE '\\')"
        params.extend([pattern, pattern])
    rows = db.execute(
        """SELECT p.id, p.user_id, p.active, u.full_name, u.email, u.role, u.avatar_stored_name, u.active AS user_active,
                  (SELECT m.id FROM messages m WHERE m.partner_id=p.id ORDER BY m.id DESC LIMIT 1) AS last_message_id,
                  (SELECT m.body FROM messages m WHERE m.partner_id=p.id ORDER BY m.id DESC LIMIT 1) AS last_message,
                  (SELECT m.created_at FROM messages m WHERE m.partner_id=p.id ORDER BY m.id DESC LIMIT 1) AS last_message_at,
                  (SELECT COUNT(*) FROM messages m
                     WHERE m.partner_id=p.id AND m.sender_user_id=p.user_id AND m.founder_read_at IS NULL) AS unread_count
           FROM partners p JOIN users u ON u.id=p.user_id""" + where +
        " ORDER BY CASE WHEN unread_count>0 THEN 0 ELSE 1 END, CASE WHEN last_message_at IS NULL THEN 1 ELSE 0 END, last_message_at DESC, u.full_name",
        params,
    ).fetchall()
    conversations = []
    for row in rows:
        item = dict(row)
        preview = (item.get("last_message") or "").strip()
        if not preview and item.get("last_message_id"):
            attachment = db.execute(
                "SELECT original_name,mime_type FROM message_attachments WHERE message_id=? ORDER BY id LIMIT 1",
                (item["last_message_id"],),
            ).fetchone()
            if attachment:
                preview = "Photo" if str(attachment["mime_type"]).startswith("image/") else attachment["original_name"]
        item["preview"] = preview or "No messages yet"
        conversations.append(item)
    return conversations


def _latest_outgoing_status(db, partner_id: int) -> dict | None:
    row = db.execute(
        """SELECT id,partner_read_at FROM messages
           WHERE partner_id=? AND sender_user_id=?
           ORDER BY id DESC LIMIT 1""",
        (partner_id, g.user["id"]),
    ).fetchone()
    if not row:
        return None
    if g.user["role"] == "admin":
        return {"message_id": row["id"], "status": "Seen" if row["partner_read_at"] else "Sent"}
    # Partners never receive or infer Founder's read state. Their own status is only Sent.
    return {"message_id": row["id"], "status": "Sent"}


def _call_duration_label(call) -> str:
    if not call["answered_at"] or not call["ended_at"]:
        return ""
    try:
        started = datetime.fromisoformat(call["answered_at"])
        ended = datetime.fromisoformat(call["ended_at"])
        seconds = max(0, int((ended - started).total_seconds()))
    except (TypeError, ValueError):
        return ""
    if seconds < 60:
        return "<1 min"
    minutes = max(1, seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, remaining = divmod(minutes, 60)
    return f"{hours} hr" if remaining == 0 else f"{hours} hr {remaining} min"


def call_event_text(call) -> str:
    if call["status"] == "DECLINED":
        return "Call declined"
    if call["status"] == "MISSED":
        return "Missed call"
    reason = call["end_reason"] if "end_reason" in call.keys() else None
    if reason == "cancelled":
        return "Call cancelled"
    if reason == "failed":
        return "Call could not connect"
    if call["answered_at"]:
        duration = _call_duration_label(call)
        return f"Voice call · {duration}" if duration else "Voice call"
    return "Call ended"


def _call_event_payload(call) -> dict:
    return {
        "id": call["id"],
        "text": call_event_text(call),
        "created_at": call["ended_at"] or call["started_at"],
    }


def _peer_profile_picture_url(partner) -> str:
    db = get_db()
    if g.user["role"] == "admin":
        if partner["avatar_stored_name"]:
            return url_for("main.profile_picture", user_id=partner["user_id"])
        return ""
    founder = db.execute(
        "SELECT id,avatar_stored_name FROM users WHERE role='admin' ORDER BY id LIMIT 1"
    ).fetchone()
    if founder and founder["avatar_stored_name"]:
        return url_for("main.profile_picture", user_id=founder["id"])
    return url_for("static", filename="images/about/key-castro.png")


def _call_payload(call, partner) -> dict:
    partner_id = int(call["partner_id"])
    base = url_for("main.messages_thread", partner_id=partner_id).rstrip("/") + "/calls/" + str(call["id"])
    peer_name = partner["full_name"] if g.user["role"] == "admin" else "Founder"
    return {
        "id": call["id"],
        "partner_id": partner_id,
        "name": peer_name,
        "avatar_url": _peer_profile_picture_url(partner),
        "status": call["status"],
        "started_by_me": call["started_by_user_id"] == g.user["id"],
        "started_at": call["started_at"],
        "answered_at": call["answered_at"],
        "ended_at": call["ended_at"],
        "end_reason": call["end_reason"] if "end_reason" in call.keys() else None,
        "updates_url": f"{base}/updates",
        "accept_url": f"{base}/accept",
        "decline_url": f"{base}/decline",
        "end_url": f"{base}/end",
        "signal_url": f"{base}/signal",
    }


def expire_stale_voice_calls() -> None:
    db = get_db()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ringing_before = (now - timedelta(seconds=60)).isoformat()
    active_before = (now - timedelta(minutes=5)).isoformat()
    active_grace = (now - timedelta(seconds=20)).isoformat()
    stale = db.execute(
        """SELECT * FROM voice_calls
           WHERE (status='RINGING' AND started_at<?)
              OR (status='ACTIVE' AND COALESCE(answered_at,started_at)<?
                  AND (COALESCE(caller_seen_at,started_at)<?
                       OR COALESCE(receiver_seen_at,answered_at,started_at)<?))""",
        (ringing_before, active_grace, active_before, active_before),
    ).fetchall()
    if not stale:
        return
    now_iso = now.isoformat()
    ids = []
    for call in stale:
        ids.append(call["id"])
        if call["status"] == "RINGING":
            db.execute(
                "UPDATE voice_calls SET status='MISSED',end_reason='missed',ended_at=? WHERE id=?",
                (now_iso, call["id"]),
            )
        else:
            db.execute(
                "UPDATE voice_calls SET status='ENDED',end_reason='connection_lost',ended_at=? WHERE id=?",
                (now_iso, call["id"]),
            )
    placeholders = ",".join("?" for _ in ids)
    db.execute(f"DELETE FROM voice_call_signals WHERE call_id IN ({placeholders})", ids)
    db.commit()


def authorized_call(partner_id: int, call_id: int):
    authorized_conversation_partner(partner_id)
    call = get_db().execute(
        "SELECT * FROM voice_calls WHERE id=? AND partner_id=?",
        (call_id, partner_id),
    ).fetchone()
    if not call:
        abort(404)
    return call


def authorized_lead(lead_id: int):
    db = get_db()
    if g.user["role"] == "admin":
        row = db.execute(
            """SELECT l.*, COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') AS owner_name FROM leads l
               JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
               WHERE l.id=?""", (lead_id,)
        ).fetchone()
    else:
        row = db.execute(
            """SELECT l.*, COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') AS owner_name FROM leads l
               JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
               WHERE l.id=? AND l.owner_partner_id=?""", (lead_id, g.partner["id"])
        ).fetchone()
    if not row:
        abort(404)
    return row


def authorized_followup(item_id: int):
    db = get_db()
    if g.user["role"] == "admin":
        row = db.execute("SELECT * FROM followups WHERE id=?", (item_id,)).fetchone()
    else:
        row = db.execute(
            """SELECT f.* FROM followups f JOIN leads l ON l.id=f.lead_id
               WHERE f.id=? AND l.owner_partner_id=? AND f.owner_partner_id=?""",
            (item_id, g.partner["id"], g.partner["id"]),
        ).fetchone()
    if not row:
        abort(404)
    return row


def authorized_sale(sale_id: int):
    db = get_db()
    sql = """SELECT s.*, l.company_name, l.contact_name, COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') AS partner_name
             FROM sales s JOIN leads l ON l.id=s.lead_id
             JOIN partners p ON p.id=s.partner_id LEFT JOIN users u ON u.id=p.user_id WHERE s.id=?"""
    params = [sale_id]
    if g.user["role"] == "partner":
        sql += " AND s.partner_id=?"
        params.append(g.partner["id"])
    row = db.execute(sql, params).fetchone()
    if not row:
        abort(404)
    return row


def authorized_commission(commission_id: int):
    db = get_db()
    sql = """SELECT c.*, s.product_service, s.client_name, s.sale_date
             FROM commissions c JOIN sales s ON s.id=c.sale_id WHERE c.id=?"""
    params = [commission_id]
    if g.user["role"] == "partner":
        sql += " AND c.partner_id=?"
        params.append(g.partner["id"])
    row = db.execute(sql, params).fetchone()
    if not row:
        abort(404)
    return row


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        validate_csrf()
        user, error = authenticate(request.form.get("email", ""), request.form.get("password", ""))
        if error:
            flash(error, "error")
        else:
            login_user(user)
            return redirect(safe_next(request.args.get("next")) or url_for("main.dashboard"))
    return render_template("login.html", title="Sign in")


@bp.post("/logout")
@login_required
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/")
@login_required
def dashboard():
    db = get_db()
    today = today_str()
    if g.user["role"] == "admin":
        sales_count = db.execute("SELECT COUNT(*) c FROM sales").fetchone()["c"]
        commissions_count = db.execute("SELECT COUNT(*) c FROM commissions").fetchone()["c"]
        leads_count = db.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
        followups_count = db.execute("SELECT COUNT(*) c FROM followups").fetchone()["c"]
        metrics = {
            "partners": db.execute("SELECT COUNT(*) c FROM partners p JOIN users u ON u.id=p.user_id").fetchone()["c"],
            "unclaimed": db.execute("SELECT COUNT(*) c FROM website_inquiries WHERE status='UNCLAIMED'").fetchone()["c"],
            "leads": leads_count,
            "new": db.execute("SELECT COUNT(*) c FROM leads WHERE status='NEW'").fetchone()["c"],
            "contacted": db.execute("SELECT COUNT(*) c FROM leads WHERE status='CONTACTED'").fetchone()["c"],
            "qualified": db.execute("SELECT COUNT(*) c FROM leads WHERE status='QUALIFIED'").fetchone()["c"],
            "demos": db.execute("SELECT COUNT(*) c FROM leads WHERE status='DEMO_BOOKED'").fetchone()["c"],
            "proposal": db.execute("SELECT COUNT(*) c FROM leads WHERE status='PROPOSAL'").fetchone()["c"],
            "won": db.execute("SELECT COUNT(*) c FROM leads WHERE status='WON'").fetchone()["c"],
            "lost": db.execute("SELECT COUNT(*) c FROM leads WHERE status='LOST'").fetchone()["c"],
            "collected": db.execute("SELECT COALESCE(SUM(collected_cents),0) c FROM sales").fetchone()["c"],
            "pending_commission": db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE status='PENDING'").fetchone()["c"],
            "approved_commission": db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE status='APPROVED'").fetchone()["c"],
            "paid_commission": db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE status='PAID'").fetchone()["c"],
            "overdue": db.execute("""SELECT COUNT(*) c FROM followups f JOIN leads l ON l.id=f.lead_id
                                      WHERE f.status='OPEN' AND f.owner_partner_id=l.owner_partner_id AND substr(f.due_at,1,10) < ?""", (today,)).fetchone()["c"],
            "due_today": db.execute("""SELECT COUNT(*) c FROM followups f JOIN leads l ON l.id=f.lead_id
                                        WHERE f.status='OPEN' AND f.owner_partner_id=l.owner_partner_id AND substr(f.due_at,1,10)=?""", (today,)).fetchone()["c"],
            "awaiting_response": db.execute("""SELECT COUNT(*) c FROM client_conversations
                                                WHERE status='ACTIVE' AND last_client_message_at IS NOT NULL
                                                  AND (last_outbound_message_at IS NULL OR last_client_message_at > last_outbound_message_at)""").fetchone()["c"],
            "duplicate_claims": db.execute("SELECT COUNT(*) c FROM duplicate_claims WHERE status='OPEN'").fetchone()["c"],
            "has_lead_data": leads_count > 0,
            "has_sales_data": sales_count > 0,
            "has_commission_data": commissions_count > 0,
            "has_followup_data": followups_count > 0,
        }
        attention = db.execute(
            """SELECT f.*, l.company_name, COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') AS partner_name FROM followups f
               JOIN leads l ON l.id=f.lead_id JOIN partners p ON p.id=f.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
               WHERE f.status='OPEN' AND f.owner_partner_id=l.owner_partner_id
               ORDER BY CASE WHEN substr(f.due_at,1,10) < ? THEN 0 ELSE 1 END, f.due_at LIMIT 8""", (today,)
        ).fetchall()
        recent = db.execute(
            """SELECT a.*, COALESCE(u.full_name,NULLIF(a.actor_name_snapshot,''),'System') actor_name FROM activity_log a
               LEFT JOIN users u ON u.id=a.actor_user_id ORDER BY a.created_at DESC LIMIT 8"""
        ).fetchall()
        partner_workloads = db.execute(
            """SELECT p.id,u.full_name,
                      (SELECT COUNT(*) FROM leads l WHERE l.owner_partner_id=p.id AND l.status NOT IN ('WON','LOST')) active_leads,
                      (SELECT COUNT(*) FROM followups f JOIN leads l ON l.id=f.lead_id
                       WHERE f.owner_partner_id=p.id AND l.owner_partner_id=p.id AND f.status='OPEN') open_followups,
                      (SELECT COUNT(*) FROM followups f JOIN leads l ON l.id=f.lead_id
                       WHERE f.owner_partner_id=p.id AND l.owner_partner_id=p.id AND f.status='OPEN' AND substr(f.due_at,1,10) < ?) overdue_followups,
                      (SELECT COUNT(*) FROM client_conversations c WHERE c.owner_partner_id=p.id AND c.status='ACTIVE') active_clients
               FROM partners p JOIN users u ON u.id=p.user_id
               WHERE p.user_id IS NOT NULL
               ORDER BY overdue_followups DESC, open_followups DESC, active_leads DESC, u.full_name
               LIMIT 8""", (today,)
        ).fetchall()
        return render_template("dashboard_admin.html", title="Dashboard", metrics=metrics, attention=attention, recent=recent, partner_workloads=partner_workloads, today=today)

    pid = g.partner["id"]
    leads_count = db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=?", (pid,)).fetchone()["c"]
    sales_count = db.execute("SELECT COUNT(*) c FROM sales WHERE partner_id=?", (pid,)).fetchone()["c"]
    commissions_count = db.execute("SELECT COUNT(*) c FROM commissions WHERE partner_id=?", (pid,)).fetchone()["c"]
    followups_count = db.execute("SELECT COUNT(*) c FROM followups WHERE owner_partner_id=?", (pid,)).fetchone()["c"]
    metrics = {
        "unclaimed": db.execute("SELECT COUNT(*) c FROM website_inquiries WHERE status='UNCLAIMED'").fetchone()["c"],
        "leads": leads_count,
        "active": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status NOT IN ('WON','LOST')", (pid,)).fetchone()["c"],
        "new": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status='NEW'", (pid,)).fetchone()["c"],
        "contacted": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status='CONTACTED'", (pid,)).fetchone()["c"],
        "qualified": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status='QUALIFIED'", (pid,)).fetchone()["c"],
        "proposal": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status='PROPOSAL'", (pid,)).fetchone()["c"],
        "lost": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status='LOST'", (pid,)).fetchone()["c"],
        "today": db.execute("""SELECT COUNT(*) c FROM followups f JOIN leads l ON l.id=f.lead_id
                              WHERE f.owner_partner_id=? AND l.owner_partner_id=? AND f.status='OPEN' AND substr(f.due_at,1,10)=?""", (pid, pid, today)).fetchone()["c"],
        "overdue": db.execute("""SELECT COUNT(*) c FROM followups f JOIN leads l ON l.id=f.lead_id
                                WHERE f.owner_partner_id=? AND l.owner_partner_id=? AND f.status='OPEN' AND substr(f.due_at,1,10)<?""", (pid, pid, today)).fetchone()["c"],
        "demos": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=? AND status='DEMO_BOOKED'", (pid,)).fetchone()["c"],
        "won": sales_count,
        "qualifying": db.execute("SELECT COALESCE(SUM(qualifying_revenue_cents),0) c FROM sales WHERE partner_id=?", (pid,)).fetchone()["c"],
        "pending": db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE partner_id=? AND status='PENDING'", (pid,)).fetchone()["c"],
        "approved": db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE partner_id=? AND status='APPROVED'", (pid,)).fetchone()["c"],
        "paid": db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE partner_id=? AND status='PAID'", (pid,)).fetchone()["c"],
        "has_lead_data": leads_count > 0,
        "has_sales_data": sales_count > 0,
        "has_commission_data": commissions_count > 0,
        "has_followup_data": followups_count > 0,
    }
    followups = db.execute(
        """SELECT f.*, l.company_name FROM followups f JOIN leads l ON l.id=f.lead_id
           WHERE f.owner_partner_id=? AND l.owner_partner_id=? AND f.status='OPEN' ORDER BY f.due_at LIMIT 8""", (pid, pid)
    ).fetchall()
    leads = db.execute(
        """SELECT l.*, (SELECT MIN(due_at) FROM followups f WHERE f.lead_id=l.id AND f.status='OPEN' AND f.owner_partner_id=l.owner_partner_id) next_followup
           FROM leads l WHERE l.owner_partner_id=? AND l.status NOT IN ('WON','LOST') ORDER BY l.last_activity_at DESC LIMIT 8""", (pid,)
    ).fetchall()
    return render_template("dashboard_partner.html", title="Dashboard", metrics=metrics, followups=followups, leads=leads, today=today)


@bp.route("/leads")
@login_required
def leads_list():
    db = get_db()
    status = request.args.get("status", "").upper()
    query = (request.args.get("q", "") or "").strip()[:120]
    params = []
    where = []
    if g.user["role"] == "partner":
        where.append("l.owner_partner_id=?")
        params.append(g.partner["id"])
    if status in PIPELINE:
        where.append("l.status=?")
        params.append(status)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        where.append("(l.company_name LIKE ? ESCAPE '\\' OR l.contact_name LIKE ? ESCAPE '\\' OR l.email LIKE ? ESCAPE '\\' OR l.phone LIKE ? ESCAPE '\\' OR l.website LIKE ? ESCAPE '\\')")
        params.extend([pattern] * 5)
    sql = """SELECT l.*, COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') owner_name,
             (SELECT MIN(due_at) FROM followups f WHERE f.lead_id=l.id AND f.status='OPEN' AND f.owner_partner_id=l.owner_partner_id) next_followup
             FROM leads l JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.last_activity_at DESC"
    rows = db.execute(sql, params).fetchall()
    return render_template("leads_list.html", title="Leads", leads=rows, pipeline=PIPELINE, selected_status=status, query=query)


@bp.route("/leads/new", methods=["GET", "POST"])
@login_required
def lead_new():
    db = get_db()
    partners = []
    if g.user["role"] == "admin":
        partners = db.execute("""SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.user_id IS NOT NULL ORDER BY u.full_name""").fetchall()
    if request.method == "POST":
        validate_csrf()
        owner_partner_id = g.partner["id"] if g.user["role"] == "partner" else request.form.get("owner_partner_id", type=int)
        data = {k: (request.form.get(k, "") or "").strip() for k in ["company_name","contact_name","email","phone","website","lead_source"]}
        initial_note = (request.form.get("summary_notes", "") or "").strip()
        errors = []
        if not owner_partner_id:
            errors.append("Choose a lead owner.")
        elif g.user["role"] == "admin" and not db.execute(
            "SELECT 1 FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.user_id IS NOT NULL",
            (owner_partner_id,),
        ).fetchone():
            errors.append("Choose a Partner.")
        if not data["company_name"]:
            errors.append("Company is required.")
        if not data["contact_name"]:
            errors.append("Contact name is required.")
        if not (data["email"] or data["phone"] or data["website"]):
            errors.append("Add an email, phone number, or website.")
        if data["email"] and not valid_email(data["email"]):
            errors.append("Enter a valid email address.")
        if data["website"] and not normalize_domain(data["website"]):
            errors.append("Enter a valid website such as example.com.")
        for key, limit in {"company_name": 200, "contact_name": 160, "email": 254, "phone": 60, "website": 300, "lead_source": 120}.items():
            if len(data[key]) > limit:
                errors.append(f"{key.replace('_', ' ').title()} must be {limit} characters or fewer.")
        matches, norms = duplicate_candidates(data) if not errors else ([], {})
        if matches:
            if g.user["role"] == "partner":
                matched, reasons = matches[0]
                if matched["owner_partner_id"] == g.partner["id"]:
                    flash("This lead is already in your list.", "warning")
                    return redirect(url_for("main.lead_detail", lead_id=matched["id"]))
                db.execute(
                    """INSERT INTO duplicate_claims(attempted_by_partner_id,matched_lead_id,company_name,contact_name,email,phone,website,reasons,status,created_at)
                       VALUES (?,?,?,?,?,?,?,?,'OPEN',?)""",
                    (g.partner["id"], matched["id"], data["company_name"], data["contact_name"], data["email"], data["phone"], data["website"], ", ".join(reasons), utcnow_iso()),
                )
                log_activity("DUPLICATE_CLAIM_BLOCKED", "lead", matched["id"], "Possible duplicate lead blocked for Founder review.", {"reasons": reasons})
                db.commit()
                flash("This lead may already exist. The Founder can review it.", "warning")
                return redirect(url_for("main.lead_new"))
            errors.append("Possible duplicate. Review the existing lead first.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("lead_form.html", title="Add Lead", partners=partners, duplicate_matches=matches if g.user["role"]=="admin" else [])
        now = utcnow_iso()
        try:
            cur = db.execute(
                """INSERT INTO leads(owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,website,website_domain,lead_source,summary_notes,status,registered_at,last_activity_at,created_by_user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'NEW',?,?,?)""",
                (owner_partner_id, data["company_name"][:200], norms["company_norm"], data["contact_name"][:160], norms["contact_norm"], data["email"][:254], norms["email_norm"], data["phone"][:60], norms["phone_norm"], data["website"][:300], norms["website_domain"], data["lead_source"][:120], "", now, now, g.user["id"]),
            )
        except (sqlite3.IntegrityError, IntegrityError):
            flash("This lead already exists, so it was not added again.", "warning")
            return redirect(url_for("main.lead_new"))
        lead_id = cur.lastrowid
        if initial_note:
            db.execute(
                "INSERT INTO lead_notes(lead_id,author_user_id,body,created_at) VALUES (?,?,?,?)",
                (lead_id, g.user["id"], initial_note[:4000], now),
            )
            log_activity("NOTE_ADDED", "lead", lead_id, "Initial note added.")
        log_activity("LEAD_CREATED", "lead", lead_id, "Lead added.", {"owner_partner_id": owner_partner_id})
        db.commit()
        flash("Lead added.", "success")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    return render_template("lead_form.html", title="Add Lead", partners=partners, duplicate_matches=[])


@bp.route("/leads/<int:lead_id>/edit", methods=["GET", "POST"])
@login_required
def lead_edit(lead_id: int):
    db = get_db()
    lead = authorized_lead(lead_id)
    if request.method == "POST":
        validate_csrf()
        data = {k: (request.form.get(k, "") or "").strip() for k in ["company_name", "contact_name", "email", "phone", "website", "lead_source"]}
        errors = []
        if not data["company_name"]:
            errors.append("Company is required.")
        if not data["contact_name"]:
            errors.append("Contact name is required.")
        if not (data["email"] or data["phone"] or data["website"]):
            errors.append("Add an email, phone number, or website.")
        if data["email"] and not valid_email(data["email"]):
            errors.append("Enter a valid email address.")
        if data["website"] and not normalize_domain(data["website"]):
            errors.append("Enter a valid website such as example.com.")
        for key, limit in {"company_name": 200, "contact_name": 160, "email": 254, "phone": 60, "website": 300, "lead_source": 120}.items():
            if len(data[key]) > limit:
                errors.append(f"{key.replace('_', ' ').title()} must be {limit} characters or fewer.")
        matches, norms = duplicate_candidates(data, exclude_lead_id=lead_id) if not errors else ([], {})
        if matches:
            if g.user["role"] == "partner":
                errors.append("These details match another lead. The Founder can review it.")
            else:
                errors.append("These details match another lead. Review it first.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("lead_edit.html", title=f"Edit {lead['company_name']}", lead=lead, duplicate_matches=matches if g.user["role"] == "admin" else [])
        now = utcnow_iso()
        try:
            db.execute(
                """UPDATE leads SET company_name=?,company_norm=?,contact_name=?,contact_norm=?,email=?,email_norm=?,phone=?,phone_norm=?,website=?,website_domain=?,lead_source=?,last_activity_at=? WHERE id=?""",
                (data["company_name"][:200], norms["company_norm"], data["contact_name"][:160], norms["contact_norm"], data["email"][:254], norms["email_norm"], data["phone"][:60], norms["phone_norm"], data["website"][:300], norms["website_domain"], data["lead_source"][:120], now, lead_id),
            )
        except (sqlite3.IntegrityError, IntegrityError):
            db.rollback()
            flash("These details match another lead. Changes were not saved.", "warning")
            return redirect(url_for("main.lead_edit", lead_id=lead_id))
        log_activity("LEAD_UPDATED", "lead", lead_id, "Lead details updated.")
        db.commit()
        flash("Lead updated.", "success")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    return render_template("lead_edit.html", title=f"Edit {lead['company_name']}", lead=lead, duplicate_matches=[])


@bp.route("/leads/<int:lead_id>")
@login_required
def lead_detail(lead_id: int):
    db = get_db()
    lead = authorized_lead(lead_id)
    if g.user["role"] == "admin":
        notes = db.execute(
            """SELECT n.*,COALESCE(u.full_name,n.author_name_snapshot,'Deleted Partner') author_name FROM lead_notes n LEFT JOIN users u ON u.id=n.author_user_id
               WHERE n.lead_id=? ORDER BY n.created_at DESC""", (lead_id,)
        ).fetchall()
        followups = db.execute(
            """SELECT f.*, COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') owner_name FROM followups f
               JOIN partners p ON p.id=f.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
               WHERE f.lead_id=? ORDER BY CASE f.status WHEN 'OPEN' THEN 0 ELSE 1 END, f.due_at""", (lead_id,)
        ).fetchall()
        activity = db.execute(
            "SELECT a.*,COALESCE(u.full_name,NULLIF(a.actor_name_snapshot,''),'System') actor_name FROM activity_log a LEFT JOIN users u ON u.id=a.actor_user_id WHERE a.entity_type='lead' AND a.entity_id=? ORDER BY a.created_at DESC LIMIT 20",
            (lead_id,),
        ).fetchall()
    else:
        notes = db.execute(
            """SELECT n.*,u.full_name author_name FROM lead_notes n JOIN users u ON u.id=n.author_user_id
               WHERE n.lead_id=? AND (n.author_user_id=? OR u.role='admin') ORDER BY n.created_at DESC""",
            (lead_id, g.user["id"]),
        ).fetchall()
        followups = db.execute(
            "SELECT * FROM followups WHERE lead_id=? AND owner_partner_id=? ORDER BY CASE status WHEN 'OPEN' THEN 0 ELSE 1 END, due_at",
            (lead_id, g.partner["id"]),
        ).fetchall()
        activity = db.execute(
            """SELECT a.*,COALESCE(u.full_name,NULLIF(a.actor_name_snapshot,''),'System') actor_name FROM activity_log a
               LEFT JOIN users u ON u.id=a.actor_user_id
               WHERE a.entity_type='lead' AND a.entity_id=?
                 AND (a.actor_user_id=? OR u.role='admin' OR a.actor_user_id IS NULL)
               ORDER BY a.created_at DESC LIMIT 20""",
            (lead_id, g.user["id"]),
        ).fetchall()
    sale = db.execute("SELECT * FROM sales WHERE lead_id=?", (lead_id,)).fetchone()
    client_conversation = db.execute(
        "SELECT * FROM client_conversations WHERE lead_id=? ORDER BY updated_at DESC,id DESC LIMIT 1", (lead_id,)
    ).fetchone()
    client_messages = []
    if client_conversation:
        client_messages = db.execute(
            """SELECT m.*,COALESCE(u.full_name,NULLIF(m.sent_by_name_snapshot,'')) sent_by_name FROM client_messages m
               LEFT JOIN users u ON u.id=m.sent_by_user_id
               WHERE m.conversation_id=? ORDER BY m.id""", (client_conversation["id"],)
        ).fetchall()
    partners = []
    if g.user["role"] == "admin":
        partners = db.execute("SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.user_id IS NOT NULL ORDER BY u.full_name").fetchall()
    return render_template("lead_detail.html", title=lead["company_name"], lead=lead, notes=notes, followups=followups, sale=sale, activity=activity, pipeline=PIPELINE, partner_allowed=PARTNER_ALLOWED_STATUSES, partners=partners, now_input=local_now_input(), client_conversation=client_conversation, client_messages=client_messages)


@bp.post("/leads/<int:lead_id>/note")
@login_required
def lead_add_note(lead_id: int):
    validate_csrf()
    authorized_lead(lead_id)
    body = (request.form.get("body", "") or "").strip()
    if not body:
        flash("Write a note before saving.", "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    db = get_db()
    db.execute("INSERT INTO lead_notes(lead_id,author_user_id,author_name_snapshot,body,created_at) VALUES (?,?,?,?,?)", (lead_id, g.user["id"], g.user["full_name"], body[:4000], utcnow_iso()))
    touch_lead(lead_id)
    log_activity("NOTE_ADDED", "lead", lead_id, "Lead note added.")
    db.commit()
    flash("Note added.", "success")
    return redirect(url_for("main.lead_detail", lead_id=lead_id))


@bp.post("/leads/<int:lead_id>/status")
@login_required
def lead_update_status(lead_id: int):
    validate_csrf()
    lead = authorized_lead(lead_id)
    status = (request.form.get("status", "") or "").upper()
    if status not in PIPELINE:
        abort(400)
    if g.user["role"] == "partner" and status not in PARTNER_ALLOWED_STATUSES:
        abort(403)
    db = get_db()
    if db.execute("SELECT 1 FROM sales WHERE lead_id=?", (lead_id,)).fetchone():
        flash("This lead is already won. Update the sale instead.", "warning")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    if status == "WON":
        flash("Create a sale to mark this lead won.", "warning")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    lost_reason = (request.form.get("lost_reason", "") or "").strip()
    demo_at_raw = (request.form.get("demo_at", "") or "").strip()
    demo_at = None
    if status == "LOST" and not lost_reason:
        flash("Add a lost reason.", "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    if status == "DEMO_BOOKED":
        if not demo_at_raw:
            flash("Add the demo date and time first.", "error")
            return redirect(url_for("main.lead_detail", lead_id=lead_id))
        try:
            demo_at = normalize_local_datetime(demo_at_raw, "Demo date and time")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.lead_detail", lead_id=lead_id))
    db.execute("UPDATE leads SET status=?,lost_reason=?,demo_at=?,last_activity_at=? WHERE id=?", (status, lost_reason[:500] if status=="LOST" else "", demo_at if status=="DEMO_BOOKED" else lead["demo_at"], utcnow_iso(), lead_id))
    log_activity("LEAD_STATUS_CHANGED", "lead", lead_id, f"Lead status changed from {lead['status'].replace('_', ' ').title()} to {status.replace('_', ' ').title()}.", {"from": lead["status"], "to": status})
    db.commit()
    flash("Status updated.", "success")
    return redirect(url_for("main.lead_detail", lead_id=lead_id))


@bp.post("/leads/<int:lead_id>/reassign")
@admin_required
def lead_reassign(lead_id: int):
    validate_csrf()
    lead = authorized_lead(lead_id)
    db = get_db()
    if db.execute("SELECT 1 FROM sales WHERE lead_id=?", (lead_id,)).fetchone():
        flash("Owner cannot change after a sale is created.", "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    new_partner = request.form.get("owner_partner_id", type=int)
    target = db.execute("SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.user_id IS NOT NULL", (new_partner,)).fetchone()
    if not target:
        abort(400)
    old_partner = lead["owner_partner_id"]
    if new_partner == old_partner:
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    now = utcnow_iso()
    db.execute("UPDATE leads SET owner_partner_id=?,last_activity_at=? WHERE id=?", (new_partner, now, lead_id))
    # Ownership moves as one business unit: lead + open follow-ups + client conversation.
    db.execute("UPDATE followups SET owner_partner_id=?,updated_at=? WHERE lead_id=? AND status='OPEN'", (new_partner, now, lead_id))
    db.execute("UPDATE client_conversations SET owner_partner_id=?,updated_at=? WHERE lead_id=?", (new_partner, now, lead_id))
    db.execute("UPDATE website_inquiries SET claimed_by_partner_id=?,updated_at=? WHERE lead_id=? AND status='CLAIMED'", (new_partner, now, lead_id))
    old_user = db.execute("SELECT user_id FROM partners WHERE id=?", (old_partner,)).fetchone()
    new_user = db.execute("SELECT user_id FROM partners WHERE id=?", (new_partner,)).fetchone()
    conversation = db.execute("SELECT id FROM client_conversations WHERE lead_id=? ORDER BY id DESC LIMIT 1", (lead_id,)).fetchone()
    if conversation and old_user:
        db.execute(
            """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
               WHERE user_id=? AND entity_type='conversation' AND entity_id=?""",
            (now, old_user["user_id"], conversation["id"]),
        )
    if conversation and new_user:
        db.execute(
            """INSERT INTO client_notifications(user_id,kind,entity_type,entity_id,title,body,created_at)
               VALUES (?,'CLIENT_REASSIGNED','conversation',?,?,'This client is now your responsibility.',?)""",
            (new_user["user_id"], conversation["id"], f"Client reassigned: {lead['company_name']}", now),
        )
    log_activity("LEAD_REASSIGNED", "lead", lead_id, "Lead, open follow-ups, and client conversation owner changed.", {"from_partner_id": old_partner, "to_partner_id": new_partner})
    db.commit()
    flash(f"Lead reassigned to {target['full_name']}.", "success")
    return redirect(url_for("main.lead_detail", lead_id=lead_id))


@bp.route("/followups")
@login_required
def followups_list():
    db = get_db()
    params = []
    where = []
    if g.user["role"] == "partner":
        where.extend(["l.owner_partner_id=?", "f.owner_partner_id=?"])
        params.extend([g.partner["id"], g.partner["id"]])
    show = request.args.get("show", "open")
    if show == "open":
        where.append("f.status='OPEN'")
    elif show == "completed":
        where.append("f.status='COMPLETED'")
    sql = """SELECT f.*,l.company_name,l.contact_name,l.owner_partner_id AS current_owner_partner_id,COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') owner_name FROM followups f
             JOIN leads l ON l.id=f.lead_id JOIN partners p ON p.id=f.owner_partner_id LEFT JOIN users u ON u.id=p.user_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE f.status WHEN 'OPEN' THEN 0 ELSE 1 END, f.due_at"
    rows = db.execute(sql, params).fetchall()
    return render_template("followups.html", title="Follow-ups", followups=rows, show=show, today=today_str())


@bp.post("/leads/<int:lead_id>/followups/new")
@login_required
def followup_new(lead_id: int):
    validate_csrf()
    lead = authorized_lead(lead_id)
    title = (request.form.get("title", "") or "").strip()
    due_at_raw = (request.form.get("due_at", "") or "").strip()
    notes = (request.form.get("notes", "") or "").strip()
    if not title or not due_at_raw:
        flash("Add a task and due date.", "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    try:
        due_at = normalize_local_datetime(due_at_raw, "Follow-up due date and time")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    db = get_db()
    now = utcnow_iso()
    cur = db.execute("""INSERT INTO followups(lead_id,owner_partner_id,title,due_at,notes,status,created_by_user_id,created_at,updated_at)
                        VALUES (?,?,?,?,?,'OPEN',?,?,?)""", (lead_id, lead["owner_partner_id"], title[:200], due_at[:30], notes[:2000], g.user["id"], now, now))
    touch_lead(lead_id)
    log_activity("FOLLOWUP_CREATED", "lead", lead_id, "Follow-up added.", {"followup_id": cur.lastrowid, "due_at": due_at})
    db.commit()
    flash("Follow-up added.", "success")
    return redirect(url_for("main.lead_detail", lead_id=lead_id))


@bp.post("/followups/<int:item_id>/complete")
@login_required
def followup_complete(item_id: int):
    validate_csrf()
    item = authorized_followup(item_id)
    if item["status"] == "COMPLETED":
        return redirect(url_for("main.lead_detail", lead_id=item["lead_id"]))
    db = get_db()
    now = utcnow_iso()
    db.execute("UPDATE followups SET status='COMPLETED',completed_at=?,updated_at=? WHERE id=?", (now, now, item_id))
    touch_lead(item["lead_id"])
    log_activity("FOLLOWUP_COMPLETED", "lead", item["lead_id"], "Follow-up completed.", {"followup_id": item_id})
    db.commit()
    flash("Follow-up completed.", "success")
    return redirect(url_for("main.lead_detail", lead_id=item["lead_id"]))


@bp.route("/sales")
@login_required
def sales_list():
    db = get_db()
    params = []
    where = ""
    if g.user["role"] == "partner":
        where = " WHERE s.partner_id=?"
        params.append(g.partner["id"])
    rows = db.execute(
        """SELECT s.*,l.company_name,COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') partner_name,c.status commission_status,c.commission_amount_cents
           FROM sales s JOIN leads l ON l.id=s.lead_id JOIN partners p ON p.id=s.partner_id LEFT JOIN users u ON u.id=p.user_id
           LEFT JOIN commissions c ON c.sale_id=s.id""" + where + " ORDER BY s.sale_date DESC,s.id DESC", params
    ).fetchall()
    return render_template("sales_list.html", title="Sales", sales=rows)


@bp.route("/sales/new", methods=["GET", "POST"])
@admin_required
def sale_new():
    db = get_db()
    lead_id = request.args.get("lead_id", type=int) or request.form.get("lead_id", type=int)
    eligible = db.execute(
        """SELECT l.id,l.company_name,l.contact_name,l.owner_partner_id,COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') owner_name
           FROM leads l JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
           LEFT JOIN sales s ON s.lead_id=l.id WHERE s.id IS NULL AND l.status!='LOST' ORDER BY l.last_activity_at DESC"""
    ).fetchall()
    lead = db.execute("""SELECT l.*,p.user_id AS owner_user_id FROM leads l JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN sales s ON s.lead_id=l.id WHERE l.id=? AND s.id IS NULL AND l.status!='LOST'""", (lead_id,)).fetchone() if lead_id else None
    if request.method == "POST":
        validate_csrf()
        if not lead:
            flash("Choose a lead that does not already have a sale.", "error")
            return render_template("sale_form.html", title="Create Sale", leads=eligible, selected_lead_id=lead_id, today=today_str())
        if not lead["owner_user_id"]:
            flash("Reassign this Lead to a current Partner before creating a sale.", "error")
            return redirect(url_for("main.lead_detail", lead_id=lead["id"]))
        product_service = (request.form.get("product_service", "") or "").strip()
        notes = (request.form.get("notes", "") or "").strip()
        payment_status = (request.form.get("payment_status", "UNPAID") or "").upper()
        sale_date_raw = (request.form.get("sale_date", "") or "").strip() or today_str()
        errors = []
        if not product_service:
            errors.append("Service is required.")
        if payment_status not in PAYMENT_STATUSES:
            errors.append("Choose a valid payment status.")
        try:
            sale_date = normalize_date(sale_date_raw, "Sale date")
        except ValueError as exc:
            errors.append(str(exc))
            sale_date = today_str()
        try:
            deal = money_to_cents(request.form.get("deal_amount"))
            invoiced = money_to_cents(request.form.get("amount_invoiced"))
            collected = money_to_cents(request.form.get("amount_collected"))
            qualifying = money_to_cents(request.form.get("qualifying_revenue"))
            if qualifying > collected:
                errors.append("Commission revenue cannot be higher than the amount collected.")
        except ValueError as exc:
            errors.append(str(exc))
            deal = invoiced = collected = qualifying = 0
        if errors:
            for e in errors: flash(e, "error")
            return render_template("sale_form.html", title="Create Sale", leads=eligible, selected_lead_id=lead_id, today=today_str())
        now = utcnow_iso()
        cur = db.execute("""INSERT INTO sales(lead_id,partner_id,client_name,product_service,deal_amount_cents,invoiced_cents,collected_cents,qualifying_revenue_cents,payment_status,sale_date,notes,created_by_user_id,created_at,updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (lead["id"], lead["owner_partner_id"], lead["company_name"], product_service[:240], deal, invoiced, collected, qualifying, payment_status, sale_date, notes[:4000], g.user["id"], now, now))
        sale_id = cur.lastrowid
        commission_id = create_commission_for_sale(sale_id, lead["owner_partner_id"], qualifying)
        db.execute("UPDATE leads SET status='WON',last_activity_at=? WHERE id=?", (now, lead["id"]))
        log_activity("SALE_CREATED", "sale", sale_id, "Sale created from lead.", {"lead_id": lead["id"], "partner_id": lead["owner_partner_id"]})
        log_activity("COMMISSION_GENERATED", "commission", commission_id, "Pending commission created.", {"sale_id": sale_id})
        log_activity("LEAD_STATUS_CHANGED", "lead", lead["id"], "Lead marked Won when sale was created.", {"from": lead["status"], "to": "WON"})
        db.commit()
        flash("Sale created. Commission pending.", "success")
        return redirect(url_for("main.sale_detail", sale_id=sale_id))
    return render_template("sale_form.html", title="Create Sale", leads=eligible, selected_lead_id=lead_id, today=today_str())


@bp.route("/sales/<int:sale_id>", methods=["GET", "POST"])
@login_required
def sale_detail(sale_id: int):
    sale = authorized_sale(sale_id)
    db = get_db()
    commission = db.execute("SELECT * FROM commissions WHERE sale_id=?", (sale_id,)).fetchone()
    if request.method == "POST":
        if g.user["role"] != "admin":
            abort(403)
        validate_csrf()
        payment_status = (request.form.get("payment_status", "") or "").upper()
        notes = (request.form.get("notes", "") or "").strip()
        errors = []
        if payment_status not in PAYMENT_STATUSES:
            errors.append("Choose a valid payment status.")
        try:
            deal = money_to_cents(request.form.get("deal_amount"))
            invoiced = money_to_cents(request.form.get("amount_invoiced"))
            collected = money_to_cents(request.form.get("amount_collected"))
            qualifying = money_to_cents(request.form.get("qualifying_revenue"))
            if qualifying > collected:
                errors.append("Commission revenue cannot be higher than the amount collected.")
            if commission and commission["status"] != "PENDING" and qualifying != commission["qualifying_revenue_cents"]:
                errors.append("Commission revenue cannot change after the commission is approved.")
        except ValueError as exc:
            errors.append(str(exc))
            deal = invoiced = collected = qualifying = 0
        if errors:
            for e in errors: flash(e, "error")
        else:
            now = utcnow_iso()
            db.execute("""UPDATE sales SET deal_amount_cents=?,invoiced_cents=?,collected_cents=?,qualifying_revenue_cents=?,payment_status=?,notes=?,updated_at=? WHERE id=?""",
                       (deal, invoiced, collected, qualifying, payment_status, notes[:4000], now, sale_id))
            sync_pending_commission(sale_id, qualifying)
            log_activity("PAYMENT_UPDATED", "sale", sale_id, "Sale payment details updated.", {"payment_status": payment_status, "collected_cents": collected, "qualifying_revenue_cents": qualifying})
            if qualifying != sale["qualifying_revenue_cents"]:
                log_activity("QUALIFYING_REVENUE_UPDATED", "sale", sale_id, "Commission revenue updated.", {"from_cents": sale["qualifying_revenue_cents"], "to_cents": qualifying})
            db.commit()
            flash("Sale updated. Pending commission recalculated.", "success")
            return redirect(url_for("main.sale_detail", sale_id=sale_id))
    sale = authorized_sale(sale_id)
    commission = db.execute("SELECT * FROM commissions WHERE sale_id=?", (sale_id,)).fetchone()
    activity = db.execute("SELECT a.*,COALESCE(u.full_name,NULLIF(a.actor_name_snapshot,''),'System') actor_name FROM activity_log a LEFT JOIN users u ON u.id=a.actor_user_id WHERE (a.entity_type='sale' AND a.entity_id=?) OR (a.entity_type='commission' AND a.entity_id=?) ORDER BY a.created_at DESC", (sale_id, commission["id"] if commission else -1)).fetchall()
    return render_template("sale_detail.html", title=sale["client_name"], sale=sale, commission=commission, payment_statuses=PAYMENT_STATUSES, activity=activity)


@bp.route("/commissions")
@login_required
def commissions_list():
    db = get_db()
    params = []
    where = ""
    if g.user["role"] == "partner":
        where = " WHERE c.partner_id=?"
        params.append(g.partner["id"])
    rows = db.execute(
        """SELECT c.*,s.client_name,s.product_service,s.sale_date,COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') partner_name
           FROM commissions c JOIN sales s ON s.id=c.sale_id JOIN partners p ON p.id=c.partner_id LEFT JOIN users u ON u.id=p.user_id""" + where + " ORDER BY c.created_at DESC", params
    ).fetchall()
    summary = {}
    if g.user["role"] == "partner":
        has_commission_data = db.execute("SELECT COUNT(*) c FROM commissions WHERE partner_id=?", (g.partner["id"],)).fetchone()["c"] > 0
        for status in ["PENDING","APPROVED","PAID"]:
            summary[status] = db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE partner_id=? AND status=?", (g.partner["id"], status)).fetchone()["c"]
    else:
        has_commission_data = db.execute("SELECT COUNT(*) c FROM commissions").fetchone()["c"] > 0
        for status in ["PENDING","APPROVED","PAID"]:
            summary[status] = db.execute("SELECT COALESCE(SUM(commission_amount_cents),0) c FROM commissions WHERE status=?", (status,)).fetchone()["c"]
    return render_template("commissions.html", title="Commissions", commissions=rows, summary=summary, has_commission_data=has_commission_data)


@bp.post("/commissions/<int:commission_id>/adjust")
@admin_required
def commission_adjust(commission_id: int):
    validate_csrf()
    commission = authorized_commission(commission_id)
    if commission["status"] != "PENDING":
        flash("Only pending commissions can be adjusted.", "error")
        return redirect(url_for("main.commissions_list"))
    try:
        adjustment = signed_money_to_cents(request.form.get("adjustment"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.commissions_list"))
    notes = (request.form.get("notes", "") or "").strip()
    amount = commission_amount(commission["qualifying_revenue_cents"], commission["rate_bp_snapshot"], adjustment)
    db = get_db()
    db.execute("UPDATE commissions SET adjustment_cents=?,commission_amount_cents=?,notes=?,updated_at=? WHERE id=?", (adjustment, amount, notes[:2000], utcnow_iso(), commission_id))
    log_activity("COMMISSION_ADJUSTED", "commission", commission_id, "Commission adjustment updated.", {"adjustment_cents": adjustment})
    db.commit()
    flash("Commission updated.", "success")
    return redirect(url_for("main.commissions_list"))


@bp.post("/commissions/<int:commission_id>/approve")
@admin_required
def commission_approve(commission_id: int):
    validate_csrf()
    commission = authorized_commission(commission_id)
    if commission["status"] != "PENDING":
        flash("Only pending commissions can be approved.", "error")
        return redirect(url_for("main.commissions_list"))
    db = get_db()
    now = utcnow_iso()
    db.execute("UPDATE commissions SET status='APPROVED',approval_date=?,updated_at=? WHERE id=?", (now, now, commission_id))
    log_activity("COMMISSION_APPROVED", "commission", commission_id, "Commission approved.")
    db.commit()
    flash("Commission approved.", "success")
    return redirect(url_for("main.commissions_list"))


@bp.post("/commissions/<int:commission_id>/paid")
@admin_required
def commission_paid(commission_id: int):
    validate_csrf()
    commission = authorized_commission(commission_id)
    if commission["status"] != "APPROVED":
        flash("Only approved commissions can be marked paid.", "error")
        return redirect(url_for("main.commissions_list"))
    db = get_db()
    now = utcnow_iso()
    db.execute("UPDATE commissions SET status='PAID',paid_date=?,updated_at=? WHERE id=?", (now, now, commission_id))
    log_activity("COMMISSION_PAID", "commission", commission_id, "Commission marked as Paid.")
    db.commit()
    flash("Commission marked paid.", "success")
    return redirect(url_for("main.commissions_list"))


@bp.route("/admin/partners")
@admin_required
def partners_list():
    db = get_db()
    rows = db.execute("""SELECT p.*,u.full_name,u.email,u.created_at account_created_at,cs.name commission_stage_name,cs.rate_bp commission_rate_bp,
        (SELECT COUNT(*) FROM leads l WHERE l.owner_partner_id=p.id) lead_count,
        (SELECT SUM(c.commission_amount_cents) FROM commissions c WHERE c.partner_id=p.id AND c.status='PAID') paid_commission
        FROM partners p JOIN users u ON u.id=p.user_id JOIN commission_stages cs ON cs.id=p.commission_stage_id
        WHERE p.user_id IS NOT NULL ORDER BY u.full_name""").fetchall()
    return render_template("partners_list.html", title="Partners", partners=rows)


@bp.route("/admin/partners/new", methods=["GET", "POST"])
@admin_required
def partner_new():
    db = get_db()
    stages = db.execute("SELECT * FROM commission_stages WHERE active=1 ORDER BY sort_order").fetchall()
    if request.method == "POST":
        validate_csrf()
        full_name = (request.form.get("full_name", "") or "").strip()
        email = (request.form.get("email", "") or "").strip().lower()
        password = request.form.get("password", "") or ""
        phone = (request.form.get("phone", "") or "").strip()
        notes = (request.form.get("notes", "") or "").strip()
        stage_id = request.form.get("commission_stage_id", type=int)
        stage = db.execute("SELECT * FROM commission_stages WHERE id=? AND active=1", (stage_id,)).fetchone()
        errors = []
        if len(full_name) < 2: errors.append("Partner name is required.")
        if not valid_email(email): errors.append("Enter a valid partner email.")
        if not valid_password(password): errors.append("Enter the Partner password you want to use.")
        if not stage: errors.append("Choose a commission level.")
        if errors:
            for e in errors: flash(e, "error")
            return render_template("partner_form.html", title="Add Partner", stages=stages)
        now = utcnow_iso()
        try:
            cur = db.execute("""INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                                VALUES (?,?,?,'partner',1,0,?,?)""", (full_name[:160], email, hash_password(password), now, now))
            user_id = cur.lastrowid
            cur = db.execute("""INSERT INTO partners(user_id,full_name_snapshot,email_snapshot,commission_stage_id,phone,notes,joined_at,active)
                                VALUES (?,?,?,?,?,?,?,1)""", (user_id, full_name[:160], email, stage_id, phone[:60], notes[:2000], now))
            partner_id = cur.lastrowid
        except (sqlite3.IntegrityError, IntegrityError):
            db.rollback()
            flash("An account with that email already exists.", "error")
            return render_template("partner_form.html", title="Add Partner", stages=stages)
        log_activity("PARTNER_CREATED", "partner", partner_id, "Partner account created.", {"stage": stage["name"], "rate_bp": stage["rate_bp"]})
        db.commit()
        return render_template("partner_created.html", title="Partner Created", partner={"id":partner_id,"full_name":full_name,"email":email}, chosen_password=password)
    return render_template("partner_form.html", title="Add Partner", stages=stages)


@bp.route("/admin/partners/<int:partner_id>", methods=["GET", "POST"])
@admin_required
def partner_detail(partner_id: int):
    db = get_db()
    partner = db.execute("""SELECT p.*,u.full_name,u.email,u.created_at account_created_at,
        cs.name commission_stage_name,cs.rate_bp commission_rate_bp
        FROM partners p JOIN users u ON u.id=p.user_id JOIN commission_stages cs ON cs.id=p.commission_stage_id
        WHERE p.id=? AND p.user_id IS NOT NULL""", (partner_id,)).fetchone()
    if not partner: abort(404)
    stages = db.execute("SELECT * FROM commission_stages WHERE active=1 ORDER BY sort_order").fetchall()
    if request.method == "POST":
        validate_csrf()
        full_name = (request.form.get("full_name", "") or "").strip()
        email = (request.form.get("email", "") or "").strip().lower()
        stage_id = request.form.get("commission_stage_id", type=int)
        phone = (request.form.get("phone", "") or "").strip()
        notes = (request.form.get("notes", "") or "").strip()
        stage = db.execute("SELECT * FROM commission_stages WHERE id=? AND active=1", (stage_id,)).fetchone()
        errors = []
        if len(full_name) < 2: errors.append("Partner name is required.")
        if not valid_email(email): errors.append("Enter a valid Partner email.")
        if not stage: errors.append("Choose a commission level.")
        if errors:
            for message in errors: flash(message, "error")
            return redirect(url_for("main.partner_detail", partner_id=partner_id))
        try:
            if stage_id != partner["commission_stage_id"]:
                log_activity("PARTNER_COMMISSION_RATE_CHANGED", "partner", partner_id, "Partner commission level changed.", {"from": partner["commission_stage_name"], "from_rate_bp": partner["commission_rate_bp"], "to": stage["name"], "to_rate_bp": stage["rate_bp"]})
            db.execute("UPDATE users SET full_name=?,email=?,updated_at=? WHERE id=?", (full_name[:160], email, utcnow_iso(), partner["user_id"]))
            db.execute("UPDATE partners SET full_name_snapshot=?,email_snapshot=?,commission_stage_id=?,phone=?,notes=? WHERE id=?", (full_name[:160], email, stage_id, phone[:60], notes[:2000], partner_id))
            log_activity("PARTNER_UPDATED", "partner", partner_id, "Partner details updated.")
            db.commit()
        except (sqlite3.IntegrityError, IntegrityError):
            db.rollback()
            flash("That email is already in use.", "error")
            return redirect(url_for("main.partner_detail", partner_id=partner_id))
        flash("Partner updated. Past commissions are unchanged.", "success")
        return redirect(url_for("main.partner_detail", partner_id=partner_id))
    stats = {
        "leads": db.execute("SELECT COUNT(*) c FROM leads WHERE owner_partner_id=?", (partner_id,)).fetchone()["c"],
        "sales": db.execute("SELECT COUNT(*) c FROM sales WHERE partner_id=?", (partner_id,)).fetchone()["c"],
        "qualifying": db.execute("SELECT SUM(qualifying_revenue_cents) c FROM sales WHERE partner_id=?", (partner_id,)).fetchone()["c"],
        "commissions": db.execute("SELECT SUM(commission_amount_cents) c FROM commissions WHERE partner_id=?", (partner_id,)).fetchone()["c"],
        "has_sales_data": db.execute("SELECT COUNT(*) c FROM sales WHERE partner_id=?", (partner_id,)).fetchone()["c"] > 0,
        "has_commission_data": db.execute("SELECT COUNT(*) c FROM commissions WHERE partner_id=?", (partner_id,)).fetchone()["c"] > 0,
    }
    return render_template("partner_detail.html", title=partner["full_name"], partner=partner, stages=stages, stats=stats)


@bp.post("/admin/partners/<int:partner_id>/reset-password")
@admin_required
def partner_reset_password(partner_id: int):
    validate_csrf()
    password = request.form.get("password", "") or ""
    if not valid_password(password):
        flash("Enter the Partner password you want to use.", "error")
        return redirect(url_for("main.partner_detail", partner_id=partner_id))
    db = get_db()
    partner = db.execute("SELECT p.*,u.full_name,u.email FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.user_id IS NOT NULL", (partner_id,)).fetchone()
    if not partner: abort(404)
    db.execute("UPDATE users SET password_hash=?,force_password_change=0,failed_login_count=0,locked_until=NULL,updated_at=? WHERE id=?", (hash_password(password), utcnow_iso(), partner["user_id"]))
    log_activity("PARTNER_PASSWORD_RESET", "partner", partner_id, "Partner password changed.")
    db.commit()
    return render_template("partner_password_changed.html", title="Password Changed", partner=partner, chosen_password=password)


@bp.post("/admin/partners/<int:partner_id>/delete")
@admin_required
def partner_delete(partner_id: int):
    validate_csrf()
    if request.form.get("confirm_delete") != "1":
        abort(400, description="Confirm permanent Partner deletion.")
    db = get_db()
    partner = db.execute(
        """SELECT p.*,u.full_name,u.email,u.avatar_stored_name
           FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.id=? AND p.user_id IS NOT NULL""",
        (partner_id,),
    ).fetchone()
    if not partner:
        abort(404)
    user_id = int(partner["user_id"])
    old_avatar = partner["avatar_stored_name"]
    now = utcnow_iso()
    try:
        # Keep only historical business attribution on the Partner row. The actual
        # authentication user, password hash, email login, and profile are deleted.
        db.execute(
            "UPDATE partners SET full_name_snapshot=?,email_snapshot='',phone='',notes='',deleted_at=? WHERE id=?",
            (partner["full_name"], now, partner_id),
        )
        db.execute(
            "UPDATE client_messages SET sent_by_name_snapshot=COALESCE(NULLIF(sent_by_name_snapshot,''),?) WHERE sent_by_user_id=?",
            (partner["full_name"], user_id),
        )
        db.execute(
            """UPDATE voice_calls SET status=CASE WHEN status='RINGING' THEN 'MISSED' ELSE 'ENDED' END,
               end_reason='partner_deleted',ended_at=?,ended_by_user_id=?
               WHERE partner_id=? AND status IN ('RINGING','ACTIVE')""",
            (now, g.user["id"], partner_id),
        )
        db.execute("DELETE FROM voice_call_signals WHERE call_id IN (SELECT id FROM voice_calls WHERE partner_id=?)", (partner_id,))
        log_activity("PARTNER_DELETED", "partner", partner_id, "Partner account permanently deleted.", {"partner_name": partner["full_name"]})
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    if old_avatar and not using_postgres():
        try:
            (_profile_picture_dir() / Path(old_avatar).name).unlink(missing_ok=True)
        except OSError:
            pass
    flash("Partner deleted permanently.", "success")
    return redirect(url_for("main.partners_list"))


@bp.route("/admin/duplicates")
@admin_required
def duplicate_claims():
    db = get_db()
    claims = db.execute("""SELECT d.*,
        COALESCE(claimant.full_name,cp.full_name_snapshot,'Deleted Partner') claimant_name,
        COALESCE(owner.full_name,op.full_name_snapshot,'Deleted Partner') owner_name,
        l.company_name matched_company
        FROM duplicate_claims d
        JOIN partners cp ON cp.id=d.attempted_by_partner_id LEFT JOIN users claimant ON claimant.id=cp.user_id
        JOIN leads l ON l.id=d.matched_lead_id JOIN partners op ON op.id=l.owner_partner_id LEFT JOIN users owner ON owner.id=op.user_id
        ORDER BY CASE d.status WHEN 'OPEN' THEN 0 ELSE 1 END,d.created_at DESC""").fetchall()
    return render_template("duplicate_claims.html", title="Duplicate Leads", claims=claims)


@bp.post("/admin/duplicates/<int:claim_id>/resolve")
@admin_required
def duplicate_resolve(claim_id: int):
    validate_csrf()
    action = request.form.get("action")
    notes = (request.form.get("resolution_notes", "") or "").strip()
    db = get_db()
    claim = db.execute("SELECT * FROM duplicate_claims WHERE id=?", (claim_id,)).fetchone()
    if not claim or claim["status"] != "OPEN": abort(404)
    lead = db.execute("SELECT * FROM leads WHERE id=?", (claim["matched_lead_id"],)).fetchone()
    if action == "reassign":
        if db.execute("SELECT 1 FROM sales WHERE lead_id=?", (lead["id"],)).fetchone():
            flash("Owner cannot change after a sale is created.", "error")
            return redirect(url_for("main.duplicate_claims"))
        old_owner = lead["owner_partner_id"]
        new_owner = claim["attempted_by_partner_id"]
        target = db.execute(
            "SELECT 1 FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.user_id IS NOT NULL",
            (new_owner,),
        ).fetchone()
        if not target:
            flash("Choose an existing Partner account.", "error")
            return redirect(url_for("main.duplicate_claims"))
        db.execute("UPDATE leads SET owner_partner_id=?,last_activity_at=? WHERE id=?", (new_owner, utcnow_iso(), lead["id"]))
        status = "REASSIGNED"
        log_activity("OWNERSHIP_OVERRIDDEN", "lead", lead["id"], "Lead owner changed after duplicate review.", {"from_partner_id": old_owner, "to_partner_id": new_owner, "duplicate_claim_id": claim_id})
    elif action == "dismiss":
        status = "DISMISSED"
        log_activity("DUPLICATE_CLAIM_RESOLVED", "lead", lead["id"], "Duplicate review kept the current owner.", {"duplicate_claim_id": claim_id})
    else:
        abort(400)
    now = utcnow_iso()
    db.execute("UPDATE duplicate_claims SET status=?,resolution_notes=?,resolved_at=?,resolved_by_user_id=? WHERE id=?", (status, notes[:1000], now, g.user["id"], claim_id))
    db.commit()
    flash("Duplicate lead reviewed.", "success")
    return redirect(url_for("main.duplicate_claims"))


def _valid_resource_url(value: str) -> bool:
    if not value:
        return True
    from urllib.parse import urlparse
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Private Founder <-> Partner communication
# ---------------------------------------------------------------------------

@bp.route("/messages")
@login_required
def messages_home():
    if g.user["role"] == "partner":
        return redirect(url_for("main.messages_thread", partner_id=g.partner["id"]))

    db = get_db()
    query = (request.args.get("q", "") or "").strip()[:120]
    partners = _founder_conversations(db, query)
    return render_template("messages_index.html", title="Messages", partners=partners, query=query)


@bp.route("/messages/<int:partner_id>")
@login_required
def messages_thread(partner_id: int):
    partner = authorized_conversation_partner(partner_id)
    expire_stale_voice_calls()
    db = get_db()
    mark_conversation_read(partner)
    db.commit()

    message_rows = db.execute(
        """SELECT m.id,m.partner_id,m.sender_user_id,m.body,m.created_at,u.full_name AS sender_name
           FROM messages m JOIN users u ON u.id=m.sender_user_id
           WHERE m.partner_id=? ORDER BY m.id DESC LIMIT 200""",
        (partner_id,),
    ).fetchall()
    attachments = _attachments_for_messages(db, partner_id, [row["id"] for row in message_rows])
    call_rows = db.execute(
        """SELECT * FROM voice_calls
           WHERE partner_id=? AND status IN ('ENDED','DECLINED','MISSED')
           ORDER BY id DESC LIMIT 100""",
        (partner_id,),
    ).fetchall()

    outgoing_status = _latest_outgoing_status(db, partner_id)
    conversation_items = []
    for row in message_rows:
        status = None
        if outgoing_status and row["id"] == outgoing_status["message_id"]:
            status = outgoing_status["status"]
        conversation_items.append({
            "kind": "message",
            "id": row["id"],
            "body": row["body"],
            "created_at": row["created_at"],
            "sender_user_id": row["sender_user_id"],
            "sender_name": row["sender_name"],
            "attachments": attachments.get(row["id"], []),
            "delivery_status": status,
        })
    for call in call_rows:
        conversation_items.append({
            "kind": "call",
            "id": call["id"],
            "text": call_event_text(call),
            "created_at": call["ended_at"] or call["started_at"],
        })
    conversation_items.sort(key=lambda item: (item["created_at"] or "", item["kind"], item["id"]))

    active_call = db.execute(
        """SELECT * FROM voice_calls WHERE partner_id=? AND status IN ('RINGING','ACTIVE')
           ORDER BY id DESC LIMIT 1""",
        (partner_id,),
    ).fetchone()
    peer_name = partner["full_name"] if g.user["role"] == "admin" else "Founder"
    founder_partners = _founder_conversations(db) if g.user["role"] == "admin" else []
    founder_user = db.execute("SELECT id,full_name,role,avatar_stored_name FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    return render_template(
        "messages_thread.html",
        title="Messages",
        partner=partner,
        conversation_items=conversation_items,
        peer_name=peer_name,
        active_call=active_call,
        founder_partners=founder_partners,
        founder_user=founder_user,
    )


@bp.post("/messages/<int:partner_id>/send")
@login_required
def message_send(partner_id: int):
    validate_csrf()
    authorized_conversation_partner(partner_id)
    body = (request.form.get("body", "") or "").strip()
    raw_files = [item for item in request.files.getlist("attachments") if item and item.filename]

    if not body and not raw_files:
        message = "Write a message or attach a file."
        if request.headers.get("X-RSF-Async") == "1":
            return jsonify({"ok": False, "error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.messages_thread", partner_id=partner_id))
    if len(body) > 2000:
        if request.headers.get("X-RSF-Async") == "1":
            return jsonify({"ok": False, "error": "Message is too long."}), 400
        flash("Message is too long.", "error")
        return redirect(url_for("main.messages_thread", partner_id=partner_id))
    if len(raw_files) > MESSAGE_MAX_ATTACHMENTS:
        message = f"Attach up to {MESSAGE_MAX_ATTACHMENTS} files at a time."
        if request.headers.get("X-RSF-Async") == "1":
            return jsonify({"ok": False, "error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.messages_thread", partner_id=partner_id))

    try:
        file_info = [_message_file_info(item) for item in raw_files]
    except ValueError as exc:
        if request.headers.get("X-RSF-Async") == "1":
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("main.messages_thread", partner_id=partner_id))
    if sum(item["size_bytes"] for item in file_info) > MESSAGE_MAX_TOTAL_BYTES:
        message = "Attachments must total 25 MB or less."
        if request.headers.get("X-RSF-Async") == "1":
            return jsonify({"ok": False, "error": message}), 400
        flash(message, "error")
        return redirect(url_for("main.messages_thread", partner_id=partner_id))

    now = utcnow_iso()
    founder_read = now if g.user["role"] == "admin" else None
    partner_read = now if g.user["role"] == "partner" else None
    db = get_db()
    saved_paths: list[Path] = []
    try:
        cur = db.execute(
            """INSERT INTO messages(partner_id,sender_user_id,body,founder_read_at,partner_read_at,created_at)
               VALUES (?,?,?,?,?,?)""",
            (partner_id, g.user["id"], body, founder_read, partner_read, now),
        )
        message_id = cur.lastrowid
        upload_dir = _message_upload_dir() if file_info and not using_postgres() else None
        for item in file_info:
            data_blob = None
            if using_postgres():
                data_blob = item["storage"].read()
                try:
                    item["storage"].stream.seek(0)
                except Exception:
                    pass
            else:
                path = upload_dir / item["stored_name"]
                item["storage"].save(path)
                saved_paths.append(path)
            db.execute(
                """INSERT INTO message_attachments(
                       message_id,partner_id,original_name,stored_name,mime_type,size_bytes,created_at,data_blob
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (message_id, partner_id, item["original_name"], item["stored_name"], item["mime_type"], item["size_bytes"], now, data_blob),
            )
        db.commit()
    except OSError:
        db.rollback()
        for path in saved_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        message = "The file could not be saved. Try again."
        if request.headers.get("X-RSF-Async") == "1":
            return jsonify({"ok": False, "error": message}), 500
        flash(message, "error")
        return redirect(url_for("main.messages_thread", partner_id=partner_id))

    if request.headers.get("X-RSF-Async") == "1":
        rows = db.execute(
            "SELECT * FROM message_attachments WHERE message_id=? ORDER BY id",
            (message_id,),
        ).fetchall()
        return jsonify({
            "ok": True,
            "message": {
                "id": message_id,
                "body": body,
                "created_at": now,
                "sender_name": g.user["full_name"],
                "mine": True,
                "attachments": [_attachment_payload(row, partner_id) for row in rows],
                "delivery_status": "Sent",
            },
        })
    return redirect(url_for("main.messages_thread", partner_id=partner_id))


@bp.get("/messages/<int:partner_id>/attachments/<int:attachment_id>")
@login_required
def message_attachment(partner_id: int, attachment_id: int):
    authorized_conversation_partner(partner_id)
    row = get_db().execute(
        """SELECT a.* FROM message_attachments a
           JOIN messages m ON m.id=a.message_id
           WHERE a.id=? AND a.partner_id=? AND m.partner_id=?""",
        (attachment_id, partner_id, partner_id),
    ).fetchone()
    if not row:
        abort(404)
    download = request.args.get("download") == "1" or not str(row["mime_type"]).startswith("image/")
    data_blob = row["data_blob"] if "data_blob" in row.keys() else None
    if data_blob is not None:
        return send_file(
            BytesIO(bytes(data_blob)), mimetype=row["mime_type"], as_attachment=download,
            download_name=row["original_name"], conditional=False, max_age=0,
        )
    path = Path(current_app.config["MESSAGE_UPLOAD_DIR"]) / row["stored_name"]
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype=row["mime_type"], as_attachment=download, download_name=row["original_name"], conditional=True, max_age=0)


@bp.get("/messages/<int:partner_id>/updates")
@login_required
def messages_updates(partner_id: int):
    partner = authorized_conversation_partner(partner_id)
    expire_stale_voice_calls()
    db = get_db()
    after_message = max(0, request.args.get("after_message", type=int) or 0)
    after_call_event = max(0, request.args.get("after_call_event", type=int) or 0)
    mark_conversation_read(partner)
    rows = db.execute(
        """SELECT m.id,m.partner_id,m.sender_user_id,m.body,m.created_at,u.full_name AS sender_name
           FROM messages m JOIN users u ON u.id=m.sender_user_id
           WHERE m.partner_id=? AND m.id>? ORDER BY m.id LIMIT 100""",
        (partner_id, after_message),
    ).fetchall()
    attachments = _attachments_for_messages(db, partner_id, [row["id"] for row in rows])
    call_events = db.execute(
        """SELECT * FROM voice_calls
           WHERE partner_id=? AND id>? AND status IN ('ENDED','DECLINED','MISSED')
           ORDER BY id LIMIT 100""",
        (partner_id, after_call_event),
    ).fetchall()
    db.commit()
    payload = {
        "messages": [
            {
                "id": row["id"],
                "body": row["body"],
                "created_at": row["created_at"],
                "sender_name": row["sender_name"],
                "mine": row["sender_user_id"] == g.user["id"],
                "attachments": attachments.get(row["id"], []),
            }
            for row in rows
        ],
        "call_events": [_call_event_payload(call) for call in call_events],
        "unread": message_unread_count(),
    }
    # The read receipt is intentionally Founder-only. Partner responses never
    # contain founder_read_at, a Founder seen flag, or any equivalent state.
    if g.user["role"] == "admin":
        status = _latest_outgoing_status(db, partner_id)
        payload["read_receipt"] = status
    return jsonify(payload)


@bp.get("/messages/unread")
@login_required
def message_unread():
    expire_stale_voice_calls()
    db = get_db()
    if g.user["role"] == "admin":
        call = db.execute(
            """SELECT c.* FROM voice_calls c
               WHERE c.status IN ('RINGING','ACTIVE')
               ORDER BY c.id DESC LIMIT 1"""
        ).fetchone()
    else:
        call = db.execute(
            """SELECT c.* FROM voice_calls c
               WHERE c.partner_id=? AND c.status IN ('RINGING','ACTIVE')
               ORDER BY c.id DESC LIMIT 1""",
            (g.partner["id"],),
        ).fetchone()

    call_data = None
    if call:
        partner = authorized_conversation_partner(call["partner_id"])
        call_data = _call_payload(call, partner)
    latest_client = db.execute(
        """SELECT id,kind,title,body,entity_type,entity_id,created_at
           FROM client_notifications WHERE user_id=? AND read_at IS NULL ORDER BY id DESC LIMIT 1""",
        (g.user["id"],),
    ).fetchone()
    return jsonify({
        "unread": message_unread_count(),
        "client_unread": client_unread_count(),
        "client_overdue": client_overdue_count(),
        "client_notification": dict(latest_client) if latest_client else None,
        "call": call_data,
    })


@bp.post("/messages/<int:partner_id>/calls/start")
@login_required
def voice_call_start(partner_id: int):
    validate_csrf()
    partner = authorized_conversation_partner(partner_id)
    expire_stale_voice_calls()
    db = get_db()
    existing = db.execute(
        """SELECT * FROM voice_calls WHERE status IN ('RINGING','ACTIVE') ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    if existing:
        if existing["partner_id"] == partner_id:
            message = "A call is already in progress."
        elif g.user["role"] == "partner":
            message = "Founder is on another call. Try again later."
        else:
            message = "Finish your current call first."
        return jsonify({"ok": False, "error": message, "call_id": existing["id"]}), 409

    now = utcnow_iso()
    try:
        cur = db.execute(
            """INSERT INTO voice_calls(
                   partner_id,started_by_user_id,status,started_at,caller_seen_at
               ) VALUES (?,?,'RINGING',?,?)""",
            (partner_id, g.user["id"], now, now),
        )
    except (sqlite3.IntegrityError, IntegrityError):
        return jsonify({"ok": False, "error": "Another call just started. Try again later."}), 409
    call_id = cur.lastrowid
    log_activity("VOICE_CALL_STARTED", "partner", partner_id, "Private voice call started.", {"call_id": call_id})
    db.commit()
    call = db.execute("SELECT * FROM voice_calls WHERE id=?", (call_id,)).fetchone()
    return jsonify({"ok": True, "call": _call_payload(call, partner)})


@bp.get("/messages/<int:partner_id>/calls/<int:call_id>/updates")
@login_required
def voice_call_updates(partner_id: int, call_id: int):
    expire_stale_voice_calls()
    call = authorized_call(partner_id, call_id)
    db = get_db()
    after_signal = max(0, request.args.get("after_signal", type=int) or 0)

    if call["status"] in {"RINGING", "ACTIVE"}:
        now = utcnow_iso()
        field = "caller_seen_at" if call["started_by_user_id"] == g.user["id"] else "receiver_seen_at"
        db.execute(f"UPDATE voice_calls SET {field}=? WHERE id=?", (now, call_id))
        db.commit()
        call = db.execute("SELECT * FROM voice_calls WHERE id=?", (call_id,)).fetchone()

    signals = []
    if call["status"] in {"RINGING", "ACTIVE"}:
        signals = db.execute(
            """SELECT id,kind,payload_json,created_at FROM voice_call_signals
               WHERE call_id=? AND id>? AND sender_user_id<>? ORDER BY id LIMIT 100""",
            (call_id, after_signal, g.user["id"]),
        ).fetchall()
    partner = authorized_conversation_partner(partner_id)
    return jsonify({
        "call": _call_payload(call, partner),
        "signals": [dict(row) for row in signals],
    })


@bp.post("/messages/<int:partner_id>/calls/<int:call_id>/accept")
@login_required
def voice_call_accept(partner_id: int, call_id: int):
    validate_csrf()
    call = authorized_call(partner_id, call_id)
    if call["status"] != "RINGING":
        return jsonify({"ok": False, "error": "This call is no longer ringing."}), 409
    if call["started_by_user_id"] == g.user["id"]:
        return jsonify({"ok": False, "error": "The other person must answer the call."}), 400
    now = utcnow_iso()
    db = get_db()
    db.execute(
        "UPDATE voice_calls SET status='ACTIVE',answered_at=?,receiver_seen_at=? WHERE id=?",
        (now, now, call_id),
    )
    log_activity("VOICE_CALL_ANSWERED", "partner", partner_id, "Private voice call answered.", {"call_id": call_id})
    db.commit()
    partner = authorized_conversation_partner(partner_id)
    call = db.execute("SELECT * FROM voice_calls WHERE id=?", (call_id,)).fetchone()
    return jsonify({"ok": True, "call": _call_payload(call, partner)})


@bp.post("/messages/<int:partner_id>/calls/<int:call_id>/decline")
@login_required
def voice_call_decline(partner_id: int, call_id: int):
    validate_csrf()
    call = authorized_call(partner_id, call_id)
    if call["status"] != "RINGING":
        return jsonify({"ok": False, "error": "This call is no longer ringing."}), 409
    if call["started_by_user_id"] == g.user["id"]:
        return jsonify({"ok": False, "error": "Use Cancel for your outgoing call."}), 400
    now = utcnow_iso()
    db = get_db()
    db.execute(
        """UPDATE voice_calls
           SET status='DECLINED',end_reason='declined',ended_at=?,ended_by_user_id=?
           WHERE id=?""",
        (now, g.user["id"], call_id),
    )
    db.execute("DELETE FROM voice_call_signals WHERE call_id=?", (call_id,))
    log_activity("VOICE_CALL_DECLINED", "partner", partner_id, "Private voice call declined.", {"call_id": call_id})
    db.commit()
    return jsonify({"ok": True, "status": "DECLINED"})


@bp.post("/messages/<int:partner_id>/calls/<int:call_id>/end")
@login_required
def voice_call_end(partner_id: int, call_id: int):
    validate_csrf()
    call = authorized_call(partner_id, call_id)
    if call["status"] not in {"RINGING", "ACTIVE"}:
        return jsonify({"ok": True, "status": call["status"]})
    if call["status"] == "RINGING" and call["started_by_user_id"] != g.user["id"]:
        return jsonify({"ok": False, "error": "Use Decline for an incoming call."}), 400

    requested_reason = (request.form.get("reason", "") or "").strip().lower()
    if call["status"] == "RINGING":
        reason = "cancelled"
    elif requested_reason in {"failed", "connection_lost"}:
        reason = requested_reason
    else:
        reason = "ended"

    now = utcnow_iso()
    db = get_db()
    db.execute(
        """UPDATE voice_calls
           SET status='ENDED',end_reason=?,ended_at=?,ended_by_user_id=?
           WHERE id=?""",
        (reason, now, g.user["id"], call_id),
    )
    db.execute("DELETE FROM voice_call_signals WHERE call_id=?", (call_id,))
    log_activity("VOICE_CALL_ENDED", "partner", partner_id, "Private voice call ended.", {"call_id": call_id, "reason": reason})
    db.commit()
    return jsonify({"ok": True, "status": "ENDED", "reason": reason})


@bp.post("/messages/<int:partner_id>/calls/<int:call_id>/signal")
@login_required
def voice_call_signal(partner_id: int, call_id: int):
    validate_csrf()
    call = authorized_call(partner_id, call_id)
    if call["status"] not in {"RINGING", "ACTIVE"}:
        return jsonify({"ok": False, "error": "This call has ended."}), 409
    kind = (request.form.get("kind", "") or "").upper()
    payload = request.form.get("payload", "") or ""
    if kind not in {"OFFER", "ANSWER", "ICE"}:
        return jsonify({"ok": False, "error": "Call could not connect."}), 400
    if len(payload) > 16000:
        return jsonify({"ok": False, "error": "Call could not connect."}), 400
    try:
        json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return jsonify({"ok": False, "error": "Call could not connect."}), 400
    if kind == "OFFER" and call["started_by_user_id"] != g.user["id"]:
        return jsonify({"ok": False, "error": "Call could not connect."}), 403
    if kind == "ANSWER" and call["started_by_user_id"] == g.user["id"]:
        return jsonify({"ok": False, "error": "Call could not connect."}), 403
    db = get_db()
    cur = db.execute(
        """INSERT INTO voice_call_signals(call_id,sender_user_id,kind,payload_json,created_at)
           VALUES (?,?,?,?,?)""",
        (call_id, g.user["id"], kind, payload, utcnow_iso()),
    )
    now = utcnow_iso()
    field = "caller_seen_at" if call["started_by_user_id"] == g.user["id"] else "receiver_seen_at"
    db.execute(f"UPDATE voice_calls SET {field}=? WHERE id=?", (now, call_id))
    db.commit()
    return jsonify({"ok": True, "signal_id": cur.lastrowid})


@bp.route("/resources")
@login_required
def resources_list():
    db = get_db()
    if g.user["role"] == "admin":
        rows = db.execute("SELECT * FROM resources ORDER BY published DESC,category,title").fetchall()
    else:
        rows = db.execute("SELECT * FROM resources WHERE published=1 ORDER BY category,title").fetchall()
    return render_template("resources.html", title="Resources", resources=rows)


@bp.route("/admin/resources/new", methods=["GET", "POST"])
@admin_required
def resource_new():
    db = get_db()
    if request.method == "POST":
        validate_csrf()
        category = request.form.get("category", "")
        title = (request.form.get("title", "") or "").strip()
        body = (request.form.get("body", "") or "").strip()
        url = (request.form.get("url", "") or "").strip()
        published = 1 if request.form.get("published") == "1" else 0
        if category not in RESOURCE_CATEGORIES or not title:
            flash("Choose a category and enter a title.", "error")
        elif not _valid_resource_url(url):
            flash("Enter a valid link starting with http:// or https://.", "error")
        else:
            now = utcnow_iso()
            cur = db.execute("INSERT INTO resources(category,title,body,url,published,created_by_user_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", (category, title[:200], body[:10000], url[:500], published, g.user["id"], now, now))
            log_activity("RESOURCE_CREATED", "resource", cur.lastrowid, "Resource added.")
            db.commit()
            flash("Resource saved.", "success")
            return redirect(url_for("main.resources_list"))
    return render_template("resource_form.html", title="Add Resource", categories=RESOURCE_CATEGORIES, resource=request.form if request.method == "POST" else None)


@bp.route("/admin/resources/<int:resource_id>/edit", methods=["GET", "POST"])
@admin_required
def resource_edit(resource_id: int):
    db = get_db()
    resource = db.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
    if not resource: abort(404)
    if request.method == "POST":
        validate_csrf()
        category = request.form.get("category", "")
        title = (request.form.get("title", "") or "").strip()
        body = (request.form.get("body", "") or "").strip()
        url = (request.form.get("url", "") or "").strip()
        published = 1 if request.form.get("published") == "1" else 0
        if category not in RESOURCE_CATEGORIES or not title:
            flash("Choose a category and enter a title.", "error")
        elif not _valid_resource_url(url):
            flash("Enter a valid link starting with http:// or https://.", "error")
        else:
            db.execute("UPDATE resources SET category=?,title=?,body=?,url=?,published=?,updated_at=? WHERE id=?", (category, title[:200], body[:10000], url[:500], published, utcnow_iso(), resource_id))
            log_activity("RESOURCE_UPDATED", "resource", resource_id, "Resource updated.")
            db.commit()
            flash("Resource updated.", "success")
            return redirect(url_for("main.resources_list"))
    return render_template("resource_form.html", title="Edit Resource", categories=RESOURCE_CATEGORIES, resource=request.form if request.method == "POST" else resource)


@bp.route("/admin/activity")
@admin_required
def activity():
    db = get_db()
    rows = db.execute("""SELECT a.*,COALESCE(u.full_name,NULLIF(a.actor_name_snapshot,''),'System') actor_name FROM activity_log a
                        LEFT JOIN users u ON u.id=a.actor_user_id ORDER BY a.created_at DESC LIMIT 500""").fetchall()
    return render_template("activity.html", title="Activity", activities=rows)


@bp.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def settings():
    db = get_db()
    stages = db.execute("SELECT * FROM commission_stages ORDER BY sort_order").fetchall()
    if request.method == "POST":
        validate_csrf()
        company = (request.form.get("company_name", "") or "").strip()[:160] or "Realty Systems Foundry"
        currency = (request.form.get("currency_code", "") or "USD").strip().upper()[:3]
        if not currency.isalpha() or len(currency) != 3:
            flash("Use a 3-letter currency such as USD or PHP.", "error")
        else:
            now = utcnow_iso()
            for key, value in [("company_name", company), ("currency_code", currency)]:
                db.execute("INSERT INTO settings(key,value,updated_at,updated_by_user_id) VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,updated_by_user_id=excluded.updated_by_user_id", (key, value, now, g.user["id"]))
            log_activity("SETTINGS_UPDATED", "settings", None, "Settings updated.")
            db.commit()
            flash("Settings updated.", "success")
            return redirect(url_for("main.settings"))
    return render_template("settings.html", title="Settings", stages=stages, company_name=setting("company_name","Realty Systems Foundry"), currency_code=setting("currency_code","USD"))


@bp.get("/profile-picture/<int:user_id>")
@login_required
def profile_picture(user_id: int):
    db = get_db()
    user = db.execute(
        "SELECT id,role,avatar_stored_name,avatar_mime_type,avatar_data FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    if not user or not _can_view_profile_picture(user):
        abort(404)
    stored_name = user["avatar_stored_name"]
    if not stored_name:
        abort(404)
    safe_name = Path(stored_name).name
    if safe_name != stored_name:
        abort(404)
    avatar_data = user["avatar_data"] if "avatar_data" in user.keys() else None
    if avatar_data is not None:
        response = send_file(BytesIO(bytes(avatar_data)), mimetype=user["avatar_mime_type"] or "application/octet-stream", as_attachment=False, conditional=False, max_age=0)
    else:
        path = _profile_picture_dir() / safe_name
        if not path.is_file():
            abort(404)
        response = send_file(path, mimetype=user["avatar_mime_type"] or "application/octet-stream", as_attachment=False, conditional=False, max_age=0)
    response.headers["Cache-Control"] = "no-store, private, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    if request.method == "POST":
        validate_csrf()
        action = request.form.get("action", "profile")
        if action == "avatar":
            storage = request.files.get("profile_picture")
            try:
                info = _profile_picture_info(storage)
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("main.profile"))
            picture_dir = _profile_picture_dir()
            new_path = picture_dir / info["stored_name"]
            old_name = g.user["avatar_stored_name"] if "avatar_stored_name" in g.user.keys() else None
            try:
                avatar_data = None
                if using_postgres():
                    avatar_data = info["storage"].read()
                    try:
                        info["storage"].stream.seek(0)
                    except Exception:
                        pass
                else:
                    info["storage"].save(new_path)
                db.execute(
                    "UPDATE users SET avatar_stored_name=?,avatar_mime_type=?,avatar_data=?,avatar_updated_at=?,updated_at=? WHERE id=?",
                    (info["stored_name"], info["mime_type"], avatar_data, utcnow_iso(), utcnow_iso(), g.user["id"]),
                )
                log_activity("PROFILE_PICTURE_UPDATED", "user", g.user["id"], "Profile picture updated.")
                db.commit()
            except Exception:
                db.rollback()
                if not using_postgres():
                    try:
                        new_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise
            if old_name and old_name != info["stored_name"]:
                try:
                    (_profile_picture_dir() / Path(old_name).name).unlink(missing_ok=True)
                except OSError:
                    pass
            flash("Profile picture updated.", "success")
            return redirect(url_for("main.profile"))
        if action == "avatar_remove":
            old_name = g.user["avatar_stored_name"] if "avatar_stored_name" in g.user.keys() else None
            db.execute(
                "UPDATE users SET avatar_stored_name=NULL,avatar_mime_type=NULL,avatar_data=NULL,avatar_updated_at=?,updated_at=? WHERE id=?",
                (utcnow_iso(), utcnow_iso(), g.user["id"]),
            )
            log_activity("PROFILE_PICTURE_REMOVED", "user", g.user["id"], "Profile picture removed.")
            db.commit()
            if old_name:
                try:
                    (_profile_picture_dir() / Path(old_name).name).unlink(missing_ok=True)
                except OSError:
                    pass
            flash("Profile picture removed.", "success")
            return redirect(url_for("main.profile"))
        if action == "password":
            if g.user["role"] != "admin":
                abort(403)
            current = request.form.get("current_password", "") or ""
            new_password = request.form.get("new_password", "") or ""
            confirm_password = request.form.get("confirm_password", "") or ""
            from werkzeug.security import check_password_hash
            if not check_password_hash(g.user["password_hash"], current):
                flash("Current password is incorrect.", "error")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "error")
            elif not valid_password(new_password):
                flash("Enter the Founder password you want to use.", "error")
            else:
                db.execute("UPDATE users SET password_hash=?,force_password_change=0,updated_at=? WHERE id=?", (hash_password(new_password), utcnow_iso(), g.user["id"]))
                log_activity("PASSWORD_CHANGED", "user", g.user["id"], "Account password changed.")
                db.commit()
                login_user(db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone())
                if g.user["role"] == "admin" and not current_app.testing:
                    try:
                        from config import BASE_DIR
                        first_access = BASE_DIR / "FIRST_RUN_FOUNDER_ACCESS.txt"
                        if first_access.exists():
                            first_access.unlink()
                    except OSError:
                        pass
                flash("Password changed.", "success")
                return redirect(url_for("main.profile"))
        else:
            full_name = (request.form.get("full_name", "") or "").strip()
            email = (request.form.get("email", "") or "").strip().lower()
            if len(full_name) < 2 or not valid_email(email):
                flash("Enter a valid name and email.", "error")
            else:
                try:
                    db.execute("UPDATE users SET full_name=?,email=?,updated_at=? WHERE id=?", (full_name[:160], email, utcnow_iso(), g.user["id"]))
                    if g.user["role"] == "partner":
                        db.execute("UPDATE partners SET phone=? WHERE id=?", ((request.form.get("phone", "") or "").strip()[:60], g.partner["id"]))
                    log_activity("PROFILE_UPDATED", "user", g.user["id"], "Profile updated.")
                    db.commit()
                    flash("Profile updated.", "success")
                    return redirect(url_for("main.profile"))
                except (sqlite3.IntegrityError, IntegrityError):
                    db.rollback()
                    flash("That email is already in use.", "error")
    return render_template("profile.html", title="Profile")

# ---------------------------------------------------------------------------
# Unified website inquiry + client conversation workspace
# ---------------------------------------------------------------------------

def _authorized_inquiry(inquiry_id: int, allow_unclaimed: bool = True):
    db = get_db()
    row = db.execute(
        """SELECT i.*,COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') claimed_by_name
           FROM website_inquiries i
           LEFT JOIN partners p ON p.id=i.claimed_by_partner_id
           LEFT JOIN users u ON u.id=p.user_id
           WHERE i.id=?""", (inquiry_id,)
    ).fetchone()
    if not row:
        abort(404)
    if g.user["role"] == "partner":
        if row["status"] == "UNCLAIMED" and allow_unclaimed:
            return row
        if not g.partner or row["claimed_by_partner_id"] != g.partner["id"]:
            abort(404)
    return row


def _authorized_client_conversation(conversation_id: int):
    db = get_db()
    row = db.execute(
        """SELECT c.*,i.status inquiry_status,i.id inquiry_record_id,l.company_name lead_company,l.status lead_status,
                  COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') owner_name
           FROM client_conversations c
           LEFT JOIN website_inquiries i ON i.client_conversation_id=c.id
           LEFT JOIN leads l ON l.id=c.lead_id
           LEFT JOIN partners p ON p.id=c.owner_partner_id
           LEFT JOIN users u ON u.id=p.user_id
           WHERE c.id=? ORDER BY i.id DESC LIMIT 1""", (conversation_id,)
    ).fetchone()
    if not row:
        abort(404)
    if g.user["role"] == "partner":
        if not g.partner or row["owner_partner_id"] != g.partner["id"]:
            abort(404)
    return row


@bp.get("/inquiries")
@login_required
def inquiries_list():
    db = get_db()
    claimed_select = """SELECT c.id AS client_conversation_id,c.lead_id,c.owner_partner_id,c.client_name AS name,
               c.client_email AS email,c.company,c.subject,c.status,c.created_at,c.updated_at,
               c.first_response_due_at,c.first_responded_at,c.last_client_message_at,c.last_outbound_message_at,
               COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') claimed_by_name,l.status AS lead_status
               FROM client_conversations c
               JOIN partners p ON p.id=c.owner_partner_id
               LEFT JOIN users u ON u.id=p.user_id
               LEFT JOIN leads l ON l.id=c.lead_id
               WHERE c.status='ACTIVE'"""
    if g.user["role"] == "admin":
        unclaimed = db.execute(
            "SELECT * FROM website_inquiries WHERE status='UNCLAIMED' ORDER BY created_at ASC"
        ).fetchall()
        claimed = db.execute(claimed_select + " ORDER BY c.updated_at DESC LIMIT 200").fetchall()
    else:
        pid = g.partner["id"]
        unclaimed = db.execute(
            "SELECT * FROM website_inquiries WHERE status='UNCLAIMED' ORDER BY created_at ASC"
        ).fetchall()
        claimed = db.execute(
            claimed_select + " AND c.owner_partner_id=? ORDER BY c.updated_at DESC LIMIT 200", (pid,)
        ).fetchall()
    partners = []
    if g.user["role"] == "admin":
        partners = db.execute(
            "SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.user_id IS NOT NULL ORDER BY u.full_name"
        ).fetchall()
    now = utcnow_iso()
    overdue = [row for row in claimed if row["first_response_due_at"] and not row["first_responded_at"] and row["first_response_due_at"] < now]
    mark_client_notifications_read()
    from .client_ops import email_receive_configured, email_send_configured
    return render_template(
        "inquiries.html", title="Client Inbox", unclaimed=unclaimed, claimed=claimed, partners=partners, overdue=overdue, current_time_iso=now,
        email_send_ready=email_send_configured(), email_receive_ready=email_receive_configured(),
        auto_email_sync=bool(current_app.config.get("AUTO_EMAIL_SYNC")),
        response_sla_minutes=int(current_app.config.get("FIRST_RESPONSE_SLA_MINUTES", 60)),
    )


@bp.get("/inquiries/<int:inquiry_id>")
@login_required
def inquiry_detail(inquiry_id: int):
    inquiry = _authorized_inquiry(inquiry_id)
    if inquiry["status"] == "CLAIMED" and inquiry["client_conversation_id"]:
        return redirect(url_for("main.client_conversation", conversation_id=inquiry["client_conversation_id"]))
    partners = []
    if g.user["role"] == "admin":
        partners = get_db().execute(
            "SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.user_id IS NOT NULL ORDER BY u.full_name"
        ).fetchall()
    matches, _normalized = duplicate_candidates({
        "company_name": inquiry["company"], "contact_name": inquiry["name"], "email": inquiry["email"],
        "phone": "", "website": "",
    })
    duplicate_leads = []
    for row, reasons in matches[:5]:
        detail = get_db().execute(
            """SELECT l.id,l.company_name,l.contact_name,l.status,COALESCE(u.full_name,p.full_name_snapshot,'Deleted Partner') owner_name
               FROM leads l JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id WHERE l.id=?""",
            (row["id"],),
        ).fetchone()
        if detail:
            duplicate_leads.append((detail, reasons))
    mark_client_notifications_read(entity_type="inquiry", entity_id=inquiry_id)
    return render_template("inquiry_detail.html", title="New Inquiry", inquiry=inquiry, partners=partners, duplicate_leads=duplicate_leads)


@bp.post("/inquiries/<int:inquiry_id>/claim")
@login_required
def inquiry_claim(inquiry_id: int):
    if g.user["role"] != "partner" or not g.partner:
        abort(403)
    _authorized_inquiry(inquiry_id)
    from .client_ops import claim_inquiry
    ok, message, conversation_id = claim_inquiry(inquiry_id, g.partner["id"], g.user["id"])
    flash(message, "success" if ok else "warning")
    if ok and conversation_id:
        return redirect(url_for("main.client_conversation", conversation_id=conversation_id))
    return redirect(url_for("main.inquiries_list"))


@bp.post("/inquiries/<int:inquiry_id>/assign")
@admin_required
def inquiry_assign(inquiry_id: int):
    _authorized_inquiry(inquiry_id)
    partner_id = request.form.get("partner_id", type=int)
    if not partner_id:
        abort(400)
    from .client_ops import assign_inquiry
    ok, message, conversation_id = assign_inquiry(inquiry_id, partner_id, g.user["id"])
    flash(message, "success" if ok else "warning")
    if conversation_id:
        return redirect(url_for("main.client_conversation", conversation_id=conversation_id))
    return redirect(url_for("main.inquiries_list"))


@bp.post("/inquiries/<int:inquiry_id>/archive")
@admin_required
def inquiry_archive(inquiry_id: int):
    inquiry = _authorized_inquiry(inquiry_id)
    if inquiry["status"] == "CLAIMED":
        flash("Claimed inquiries stay with their client record. Close the lead instead.", "warning")
        return redirect(url_for("main.client_conversation", conversation_id=inquiry["client_conversation_id"]))
    db = get_db()
    now = utcnow_iso()
    db.execute("UPDATE website_inquiries SET status='ARCHIVED',updated_at=? WHERE id=?", (now, inquiry_id))
    db.execute("""UPDATE client_notifications SET read_at=COALESCE(read_at,?)
                  WHERE entity_type='inquiry' AND entity_id=?""", (now, inquiry_id))
    db.commit()
    flash("Inquiry archived.", "success")
    return redirect(url_for("main.inquiries_list"))


def _client_attachments_for_messages(db, message_ids) -> dict[int, list]:
    ids = [int(value) for value in message_ids if value]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"SELECT * FROM client_attachments WHERE message_id IN ({placeholders}) ORDER BY message_id,id",
        ids,
    ).fetchall()
    result: dict[int, list] = {}
    for row in rows:
        result.setdefault(int(row["message_id"]), []).append(row)
    return result


@bp.get("/clients/<int:conversation_id>")
@login_required
def client_conversation(conversation_id: int):
    conv = _authorized_client_conversation(conversation_id)
    db = get_db()
    messages = db.execute(
        """SELECT m.*,COALESCE(u.full_name,NULLIF(m.sent_by_name_snapshot,'')) sent_by_name FROM client_messages m
           LEFT JOIN users u ON u.id=m.sent_by_user_id
           WHERE m.conversation_id=? ORDER BY m.id""", (conversation_id,)
    ).fetchall()
    attachments = _client_attachments_for_messages(db, [m["id"] for m in messages])
    mark_client_notifications_read(entity_type="conversation", entity_id=conversation_id)
    from .client_ops import email_receive_configured, email_send_configured
    now_iso = utcnow_iso()
    is_overdue = bool(conv["first_response_due_at"] and not conv["first_responded_at"] and conv["first_response_due_at"] < now_iso)
    return render_template(
        "client_conversation.html", title=conv["company"] or conv["client_name"], conversation=conv,
        client_messages=messages, client_attachments=attachments,
        email_send_ready=email_send_configured(), email_receive_ready=email_receive_configured(),
        auto_email_sync=bool(current_app.config.get("AUTO_EMAIL_SYNC")), is_overdue=is_overdue,
        client_max_attachments=int(current_app.config.get("CLIENT_MAX_ATTACHMENTS", 5)),
    )


@bp.get("/clients/attachments/<int:attachment_id>")
@login_required
def client_attachment(attachment_id: int):
    db = get_db()
    row = db.execute(
        """SELECT a.*,m.conversation_id FROM client_attachments a
           JOIN client_messages m ON m.id=a.message_id WHERE a.id=?""", (attachment_id,)
    ).fetchone()
    if not row:
        abort(404)
    _authorized_client_conversation(int(row["conversation_id"]))
    data_blob = row["data_blob"] if "data_blob" in row.keys() else None
    if data_blob is not None:
        return send_file(BytesIO(bytes(data_blob)), mimetype=row["mime_type"], as_attachment=True, download_name=row["original_name"], max_age=0)
    path = Path(current_app.config["CLIENT_ATTACHMENT_DIR"]) / row["stored_name"]
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype=row["mime_type"], as_attachment=True, download_name=row["original_name"], max_age=0)


@bp.post("/clients/<int:conversation_id>/reply")
@login_required
def client_reply(conversation_id: int):
    _authorized_client_conversation(conversation_id)
    body = (request.form.get("body", "") or "").strip()
    files = request.files.getlist("attachments")
    from .client_ops import send_client_email
    try:
        send_client_email(conversation_id, g.user["id"], body, files)
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")
    except Exception:
        current_app.logger.exception("Client email send failed")
        flash("RSF could not send that email. Check the official email configuration and try again.", "error")
    else:
        flash("Reply sent from the official RSF email.", "success")
    return redirect(url_for("main.client_conversation", conversation_id=conversation_id))


@bp.post("/clients/sync-email")
@login_required
def client_sync_email():
    from .client_ops import sync_inbound_email
    try:
        result = sync_inbound_email()
    except RuntimeError as exc:
        flash(str(exc), "warning")
    except Exception:
        current_app.logger.exception("Client email sync failed")
        flash("Could not sync the official RSF mailbox right now.", "error")
    else:
        extra = f" {result.get('bounced', 0)} bounce(s) detected." if result.get("bounced") else ""
        flash(f"Email synced. {result['imported']} new message(s) imported.{extra}", "success")
    return redirect(request.referrer or url_for("main.inquiries_list"))
