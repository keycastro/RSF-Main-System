from __future__ import annotations

import email
import imaplib
import mimetypes
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from html.parser import HTMLParser
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Any

from flask import current_app

from .db import get_db, using_postgres
from .record_ops import find_matching_prospect
from .services import file_signature_matches, log_activity, normalize_email, normalize_text, utcnow_iso


class _PlainTextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join((data or "").split())
        if text:
            self.parts.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def text(self) -> str:
        out = " ".join(self.parts)
        out = out.replace(" \n ", "\n").replace(" \n", "\n").replace("\n ", "\n")
        return "\n".join(line.strip() for line in out.splitlines() if line.strip()).strip()


def _decode_part(part) -> str:
    try:
        return part.get_content().strip()
    except Exception:
        payload = part.get_payload(decode=True) or b""
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()


def _html_to_text(value: str) -> str:
    parser = _PlainTextHTML()
    try:
        parser.feed(value or "")
        parser.close()
        return parser.text()
    except Exception:
        return ""


def _text_part(message) -> str:
    """Read safe plain text. HTML-only messages are converted to text, never rendered as raw HTML."""
    html_fallback = ""
    if message.is_multipart():
        for part in message.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                text = _decode_part(part)
                if text:
                    return text
            elif ctype == "text/html" and not html_fallback:
                html_fallback = _decode_part(part)
        return _html_to_text(html_fallback) if html_fallback else ""
    ctype = message.get_content_type()
    text = _decode_part(message)
    return _html_to_text(text) if ctype == "text/html" else text


def email_send_configured() -> bool:
    return bool(
        current_app.config.get("RSF_EMAIL_ADDRESS")
        and current_app.config.get("SMTP_HOST")
        and current_app.config.get("SMTP_USERNAME")
        and current_app.config.get("SMTP_PASSWORD")
    )


def email_receive_configured() -> bool:
    return bool(
        current_app.config.get("RSF_EMAIL_ADDRESS")
        and current_app.config.get("IMAP_HOST")
        and current_app.config.get("IMAP_USERNAME")
        and current_app.config.get("IMAP_PASSWORD")
    )


CLIENT_FILE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".pdf": "application/pdf", ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".csv": "text/csv", ".txt": "text/plain", ".rtf": "application/rtf",
}


def _attachment_dir() -> Path:
    path = Path(current_app.config["CLIENT_ATTACHMENT_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _founder_user_ids() -> list[int]:
    return [int(row["id"]) for row in get_db().execute("SELECT id FROM users WHERE role='admin' AND active=1").fetchall()]


def _partner_user_id(partner_id: int | None) -> int | None:
    if not partner_id:
        return None
    row = get_db().execute("SELECT user_id FROM partners WHERE id=?", (partner_id,)).fetchone()
    return int(row["user_id"]) if row else None


def _notify(user_id: int | None, kind: str, title: str, body: str = "", *, entity_type: str = "", entity_id: int | None = None) -> None:
    if not user_id:
        return
    get_db().execute(
        """INSERT INTO client_notifications(user_id,kind,entity_type,entity_id,title,body,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (int(user_id), kind[:60], entity_type[:40], entity_id, title[:180], body[:500], utcnow_iso()),
    )


def _notify_founders(kind: str, title: str, body: str = "", *, entity_type: str = "", entity_id: int | None = None) -> None:
    for user_id in _founder_user_ids():
        _notify(user_id, kind, title, body, entity_type=entity_type, entity_id=entity_id)


def _notify_all_active_partners(kind: str, title: str, body: str = "", *, entity_type: str = "", entity_id: int | None = None) -> None:
    rows = get_db().execute(
        """SELECT u.id FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.active=1 AND u.active=1"""
    ).fetchall()
    for row in rows:
        _notify(int(row["id"]), kind, title, body, entity_type=entity_type, entity_id=entity_id)


def _dismiss_inquiry_notifications(inquiry_id: int, *, except_user_id: int | None = None) -> None:
    db = get_db()
    now = utcnow_iso()
    if except_user_id:
        db.execute(
            """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
               WHERE entity_type='inquiry' AND entity_id=? AND user_id<>?""",
            (now, inquiry_id, except_user_id),
        )
    else:
        db.execute(
            """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
               WHERE entity_type='inquiry' AND entity_id=?""",
            (now, inquiry_id),
        )


def _sla_due(now_iso: str) -> str:
    minutes = int(current_app.config.get("FIRST_RESPONSE_SLA_MINUTES", 60))
    base = datetime.fromisoformat(now_iso)
    return (base + timedelta(minutes=minutes)).isoformat()


def _safe_attachment_name(filename: str) -> str:
    name = Path(filename or "attachment").name.replace("\x00", "").strip() or "attachment"
    return name[:180]


def _store_attachment_bytes(message_id: int, filename: str, data: bytes, mime_type: str = "") -> int | None:
    if not data:
        return None
    max_file = int(current_app.config.get("CLIENT_MAX_FILE_MB", 15)) * 1024 * 1024
    if len(data) > max_file:
        return None
    original = _safe_attachment_name(filename)
    suffix = Path(original).suffix.lower()
    guessed = CLIENT_FILE_TYPES.get(suffix) or mimetypes.guess_type(original)[0] or "application/octet-stream"
    if suffix not in CLIENT_FILE_TYPES:
        return None
    if not file_signature_matches(suffix, data):
        return None
    stored = f"{uuid.uuid4().hex}{suffix}"
    data_blob = data if using_postgres() else None
    if not using_postgres():
        path = _attachment_dir() / stored
        path.write_bytes(data)
    cur = get_db().execute(
        """INSERT INTO client_attachments(message_id,original_name,stored_name,mime_type,size_bytes,created_at,data_blob)
           VALUES (?,?,?,?,?,?,?)""",
        (message_id, original, stored, mime_type or guessed, len(data), utcnow_iso(), data_blob),
    )
    return int(cur.lastrowid)


def _prepare_outbound_attachments(storages) -> list[tuple[str, str, bytes]]:
    items: list[tuple[str, str, bytes]] = []
    max_count = int(current_app.config.get("CLIENT_MAX_ATTACHMENTS", 5))
    max_file = int(current_app.config.get("CLIENT_MAX_FILE_MB", 15)) * 1024 * 1024
    max_total = int(current_app.config.get("CLIENT_MAX_TOTAL_MB", 25)) * 1024 * 1024
    total = 0
    for storage in list(storages or [])[: max_count + 1]:
        if storage is None or not getattr(storage, "filename", ""):
            continue
        if len(items) >= max_count:
            raise ValueError(f"Attach up to {max_count} files.")
        name = _safe_attachment_name(storage.filename)
        suffix = Path(name).suffix.lower()
        if suffix not in CLIENT_FILE_TYPES:
            raise ValueError(f"File type not allowed: {name}")
        data = storage.read()
        try:
            storage.stream.seek(0)
        except Exception:
            pass
        if not data:
            raise ValueError(f"Attachment is empty: {name}")
        if not file_signature_matches(suffix, data):
            raise ValueError(f"File content does not match its type: {name}")
        if len(data) > max_file:
            raise ValueError(f"Each client attachment must be {current_app.config.get('CLIENT_MAX_FILE_MB', 15)} MB or smaller.")
        total += len(data)
        if total > max_total:
            raise ValueError(f"Total client attachments must be {current_app.config.get('CLIENT_MAX_TOTAL_MB', 25)} MB or smaller.")
        items.append((name, CLIENT_FILE_TYPES[suffix], data))
    return items


def _extract_inbound_attachments(message) -> list[tuple[str, str, bytes]]:
    items: list[tuple[str, str, bytes]] = []
    max_count = int(current_app.config.get("CLIENT_MAX_ATTACHMENTS", 5))
    max_total = int(current_app.config.get("CLIENT_MAX_TOTAL_MB", 25)) * 1024 * 1024
    total = 0
    for part in message.walk() if message.is_multipart() else []:
        filename = part.get_filename()
        if not filename:
            continue
        if len(items) >= max_count:
            break
        try:
            filename = str(make_header(decode_header(filename)))
        except Exception:
            pass
        original = _safe_attachment_name(filename)
        suffix = Path(original).suffix.lower()
        if suffix not in CLIENT_FILE_TYPES:
            continue
        data = part.get_payload(decode=True) or b""
        if not data or not file_signature_matches(suffix, data):
            continue
        total += len(data)
        if total > max_total:
            break
        items.append((original, part.get_content_type() or CLIENT_FILE_TYPES[suffix], data))
    return items


def _active_partner(partner_id: int):
    return get_db().execute(
        """SELECT p.id,p.user_id,u.full_name,u.active AS user_active,p.active AS partner_active
           FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.id=? AND p.active=1 AND u.active=1""",
        (partner_id,),
    ).fetchone()


def _find_exact_email_lead(email_value: str):
    email_norm = normalize_email(email_value)
    if not email_norm:
        return None
    return get_db().execute(
        """SELECT l.*,p.active AS partner_active,u.active AS user_active
           FROM leads l JOIN partners p ON p.id=l.owner_partner_id JOIN users u ON u.id=p.user_id
           WHERE l.email_norm=? AND l.status NOT IN ('WON','LOST') ORDER BY l.last_activity_at DESC,l.id DESC LIMIT 1""",
        (email_norm,),
    ).fetchone()


def _conversation_for_lead(lead_id: int):
    return get_db().execute(
        "SELECT * FROM client_conversations WHERE lead_id=? ORDER BY id DESC LIMIT 1", (lead_id,)
    ).fetchone()


def _conversation_for_prospect(prospect_id: int):
    return get_db().execute(
        "SELECT * FROM client_conversations WHERE prospect_id=? AND status='ACTIVE' ORDER BY id DESC LIMIT 1",
        (prospect_id,),
    ).fetchone()


def _create_conversation(*, inquiry_id: int | None, lead_id: int | None, owner_partner_id: int | None,
                         name: str, email_value: str, company: str, subject: str = "",
                         prospect_id: int | None = None) -> int:
    db = get_db()
    now = utcnow_iso()
    cur = db.execute(
        """INSERT INTO client_conversations
           (inquiry_id,prospect_id,lead_id,owner_partner_id,client_name,client_email,company,subject,status,created_at,updated_at,last_client_message_at)
           VALUES (?,?,?,?,?,?,?,?,'ACTIVE',?,?,?)""",
        (
            inquiry_id,
            prospect_id,
            lead_id,
            owner_partner_id,
            name[:100],
            email_value[:254],
            company[:140],
            subject[:240],
            now,
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def ensure_prospect_conversation(prospect_id: int, owner_partner_id: int | None = None) -> int:
    """Create/reuse the official-email conversation for one outbound Prospect."""
    db = get_db()
    prospect = db.execute(
        "SELECT id,name,contact,email FROM prospects WHERE id=?",
        (prospect_id,),
    ).fetchone()
    if not prospect:
        raise ValueError("Prospect not found.")
    email_value = (prospect["email"] or "").strip()
    if not email_value:
        raise ValueError("Add the Prospect email before opening Email.")

    existing = _conversation_for_prospect(prospect_id)
    if existing:
        conversation_id = int(existing["id"])
        db.execute(
            """UPDATE client_conversations
               SET client_name=?,client_email=?,company=?,
                   owner_partner_id=COALESCE(owner_partner_id,?),updated_at=?
               WHERE id=?""",
            (
                (prospect["contact"] or prospect["name"] or "")[:100],
                email_value[:254],
                (prospect["name"] or "")[:140],
                owner_partner_id,
                utcnow_iso(),
                conversation_id,
            ),
        )
        db.commit()
        return conversation_id

    conversation_id = _create_conversation(
        inquiry_id=None,
        prospect_id=prospect_id,
        lead_id=None,
        owner_partner_id=owner_partner_id,
        name=(prospect["contact"] or prospect["name"] or ""),
        email_value=email_value,
        company=(prospect["name"] or ""),
        subject="RSF outreach",
    )
    db.commit()
    return conversation_id


def create_public_inquiry(record: dict[str, str]) -> int:
    """Store public contact inside the unified client journey.

    Repeated submissions from the same email stay inside the same active Website
    Inquiry. A closed engagement creates a new Inquiry. If an active Researched
    Prospect already represents the client, the Website source joins that journey.
    """
    db = get_db()
    now = utcnow_iso()
    name = (record.get("name") or "").strip()[:100]
    email_value = (record.get("email") or "").strip()[:254]
    email_norm = normalize_email(email_value)
    phone = (record.get("phone") or "").strip()[:40]
    company = (record.get("company") or "").strip()[:140]
    message = (record.get("message") or "").strip()[:10000]
    source_type = (record.get("source_type") or "")[:40]
    source_slug = (record.get("source_slug") or "")[:160]
    source_title = (record.get("source_title") or "")[:200]
    source_action = (record.get("source_action") or "")[:80]

    active_inquiry = None
    if email_norm:
        active_inquiry = db.execute(
            """SELECT * FROM website_inquiries
               WHERE email_norm=?
                 AND status NOT IN ('ARCHIVED','SPAM')
                 AND workflow_status NOT IN ('REJECTED','WON','LOST')
               ORDER BY updated_at DESC,id DESC
               LIMIT 1""",
            (email_norm,),
        ).fetchone()

    if active_inquiry:
        inquiry_id = int(active_inquiry["id"])
        conversation_id = int(active_inquiry["client_conversation_id"] or 0)
        if not conversation_id:
            conversation_id = _create_conversation(
                inquiry_id=inquiry_id,
                lead_id=active_inquiry["lead_id"],
                owner_partner_id=active_inquiry["claimed_by_partner_id"],
                name=name,
                email_value=email_value,
                company=company,
                subject="Website inquiry to Realty Systems Foundry",
            )
        db.execute(
            """UPDATE website_inquiries
               SET updated_at=?,name=?,email=?,email_norm=?,phone=?,company=?,message=?,
                   source_type=?,source_slug=?,source_title=?,source_action=?,client_conversation_id=?
               WHERE id=?""",
            (
                now, name, email_value, email_norm, phone, company, message,
                source_type, source_slug, source_title, source_action, conversation_id, inquiry_id,
            ),
        )
        db.execute(
            """UPDATE client_conversations
               SET updated_at=?,client_name=?,client_email=?,company=?,last_client_message_at=?
               WHERE id=?""",
            (now, name, email_value, company, now, conversation_id),
        )
        db.execute(
            """INSERT INTO client_messages
               (conversation_id,direction,channel,journey_source,sender_email,recipient_email,subject,body,created_at,delivery_status)
               VALUES (?,'INBOUND','WEBSITE','INBOUND',?,?,?, ?,?,'RECEIVED')""",
            (
                conversation_id,
                email_value,
                current_app.config.get("RSF_EMAIL_ADDRESS", ""),
                "Website inquiry",
                message,
                now,
            ),
        )

        owner_partner_id = active_inquiry["claimed_by_partner_id"]
        title = f"{company or name} sent another website message"
        if owner_partner_id:
            owner_user_id = _partner_user_id(int(owner_partner_id))
            _notify(owner_user_id, "CLIENT_REPLY", title, "A new Website message was added to the active client conversation.", entity_type="conversation", entity_id=conversation_id)
            _notify_founders("CLIENT_REPLY", title, "A new Website message was added to the active client conversation.", entity_type="conversation", entity_id=conversation_id)
        else:
            _notify_all_active_partners("NEW_INQUIRY", title, "A new message was added to an active unclaimed Website Inquiry.", entity_type="inquiry", entity_id=inquiry_id)
            _notify_founders("NEW_INQUIRY", title, "A new message was added to an active Website Inquiry.", entity_type="inquiry", entity_id=inquiry_id)
        if active_inquiry["lead_id"]:
            db.execute("UPDATE leads SET last_activity_at=? WHERE id=?", (now, active_inquiry["lead_id"]))
        db.commit()
        return inquiry_id

    identity = {
        "company": company,
        "contact_name": name,
        "email": email_value,
        "phone": phone,
    }
    matched_prospect = find_matching_prospect(db, identity)
    active_prospect = matched_prospect if matched_prospect and (matched_prospect["status"] or "").upper() not in ("REJECTED", "WON", "LOST") else None

    existing = _find_exact_email_lead(email_value)
    owner_partner_id = None
    lead_id = None
    status = "UNCLAIMED"
    if existing and existing["partner_active"] and existing["user_active"]:
        owner_partner_id = int(existing["owner_partner_id"])
        lead_id = int(existing["id"])
        status = "CLAIMED"

    cur = db.execute(
        """INSERT INTO website_inquiries
           (created_at,updated_at,name,email,email_norm,phone,company,message,status,claimed_by_partner_id,claimed_at,lead_id,
            source_type,source_slug,source_title,source_action)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            now, now, name, email_value, email_norm, phone, company, message, status,
            owner_partner_id, now if owner_partner_id else None, lead_id,
            source_type, source_slug, source_title, source_action,
        ),
    )
    inquiry_id = int(cur.lastrowid)

    conversation = _conversation_for_prospect(int(active_prospect["id"])) if active_prospect else None
    if not conversation and lead_id:
        conversation = _conversation_for_lead(lead_id)
    if conversation:
        conversation_id = int(conversation["id"])
        db.execute(
            """UPDATE client_conversations
               SET inquiry_id=?,updated_at=?,client_name=?,client_email=?,company=?,last_client_message_at=?
               WHERE id=?""",
            (inquiry_id, now, name, email_value, company, now, conversation_id),
        )
    else:
        conversation_id = _create_conversation(
            inquiry_id=inquiry_id,
            prospect_id=int(active_prospect["id"]) if active_prospect else None,
            lead_id=lead_id,
            owner_partner_id=owner_partner_id,
            name=name,
            email_value=email_value,
            company=company,
            subject="Website inquiry to Realty Systems Foundry",
        )
    db.execute("UPDATE website_inquiries SET client_conversation_id=? WHERE id=?", (conversation_id, inquiry_id))
    db.execute(
        """INSERT INTO client_messages
           (conversation_id,direction,channel,journey_source,sender_email,recipient_email,subject,body,created_at,delivery_status)
           VALUES (?,'INBOUND','WEBSITE','INBOUND',?,?,?, ?,?,'RECEIVED')""",
        (
            conversation_id,
            email_value,
            current_app.config.get("RSF_EMAIL_ADDRESS", ""),
            "Website inquiry",
            message,
            now,
        ),
    )

    # If Research already has an active Deal for this same opportunity, attach
    # the new Website source to that Deal instead of creating a second pipeline.
    if active_prospect and (active_prospect["status"] or "").upper() in ("DEAL", "DEMO", "PROPOSAL", "DECISION"):
        existing_deal = db.execute(
            "SELECT id,website_inquiry_id FROM deals WHERE prospect_id=? LIMIT 1",
            (active_prospect["id"],),
        ).fetchone()
        if existing_deal and existing_deal["website_inquiry_id"] is None:
            shared_status = (active_prospect["status"] or "DEAL").upper()
            db.execute(
                """UPDATE deals
                   SET website_inquiry_id=?,
                       contact_number=CASE WHEN trim(contact_number)='' THEN ? ELSE contact_number END,
                       email=CASE WHEN trim(email)='' THEN ? ELSE email END,
                       updated_at=?
                   WHERE id=?""",
                (inquiry_id, phone[:120], email_value[:320], now, existing_deal["id"]),
            )
            db.execute(
                "UPDATE website_inquiries SET workflow_status=?,updated_at=? WHERE id=?",
                (shared_status, now, inquiry_id),
            )
            log_activity(
                "DEAL_SOURCE_MERGED",
                "deal",
                int(existing_deal["id"]),
                "Website Inquiry linked to the existing Research Deal.",
                {"prospect_id": int(active_prospect["id"]), "website_inquiry_id": inquiry_id},
            )

    if lead_id:
        db.execute("UPDATE leads SET last_activity_at=? WHERE id=?", (now, lead_id))
        db.execute(
            """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
               VALUES (NULL,'CLIENT_RETURNED','lead',?,'Existing lead sent a new website inquiry.','{}',?)""",
            (lead_id, now),
        )
        owner_user_id = _partner_user_id(owner_partner_id)
        _notify(owner_user_id, "CLIENT_REPLY", f"{company or name} contacted RSF again", "A returning client sent a new website message.", entity_type="conversation", entity_id=conversation_id)
        _notify_founders("CLIENT_REPLY", f"{company or name} contacted RSF again", "A returning client sent a new website message.", entity_type="conversation", entity_id=conversation_id)
    else:
        title = f"New inquiry: {company or name}"
        _notify_all_active_partners("NEW_INQUIRY", title, "A new unclaimed website opportunity is available.", entity_type="inquiry", entity_id=inquiry_id)
        _notify_founders("NEW_INQUIRY", title, "A new unclaimed website opportunity is available.", entity_type="inquiry", entity_id=inquiry_id)
    db.commit()
    return inquiry_id


def claim_inquiry(inquiry_id: int, partner_id: int, actor_user_id: int) -> tuple[bool, str, int | None]:
    """Atomically claim an unclaimed inquiry and create/link its CRM lead."""
    db = get_db()
    partner = _active_partner(partner_id)
    if not partner:
        return False, "Partner is not active.", None
    inquiry = db.execute("SELECT * FROM website_inquiries WHERE id=?", (inquiry_id,)).fetchone()
    if not inquiry:
        return False, "Inquiry not found.", None
    if inquiry["status"] != "UNCLAIMED" or inquiry["claimed_by_partner_id"] is not None:
        return False, "This inquiry has already been claimed.", inquiry["client_conversation_id"]

    # Re-check exact email ownership at claim time. This closes the race where a
    # matching lead was created after the public inquiry first arrived.
    existing = _find_exact_email_lead(inquiry["email"])
    now = utcnow_iso()
    if existing and (not existing["partner_active"] or not existing["user_active"]):
        _notify_founders("OWNERSHIP_REVIEW", f"Ownership review needed: {inquiry['company'] or inquiry['name']}",
                         "This contact matches an active Lead whose Partner account is inactive. Reassign that Lead before claiming this inquiry.",
                         entity_type="inquiry", entity_id=inquiry_id)
        db.commit()
        return False, "This contact already has an RSF lead with an inactive owner. Founder must reassign that lead first.", inquiry["client_conversation_id"]
    if existing:
        owner_id = int(existing["owner_partner_id"])
        conversation = _conversation_for_lead(int(existing["id"]))
        conversation_id = int(inquiry["client_conversation_id"])
        if conversation and int(conversation["id"]) != conversation_id:
            # Move the original website message into the established client history.
            db.execute("UPDATE client_messages SET conversation_id=? WHERE conversation_id=?", (conversation["id"], conversation_id))
            db.execute("DELETE FROM client_conversations WHERE id=?", (conversation_id,))
            conversation_id = int(conversation["id"])
        else:
            db.execute(
                """UPDATE client_conversations SET lead_id=?,owner_partner_id=?,updated_at=?,
                   first_response_due_at=COALESCE(first_response_due_at,?) WHERE id=?""",
                (existing["id"], owner_id, now, _sla_due(now), conversation_id),
            )
        claim_result = db.execute(
            """UPDATE website_inquiries SET status='CLAIMED',claimed_by_partner_id=?,claimed_at=?,lead_id=?,
               client_conversation_id=?,updated_at=? WHERE id=? AND status='UNCLAIMED'
               AND claimed_by_partner_id IS NULL""",
            (owner_id, now, existing["id"], conversation_id, now, inquiry_id),
        )
        if claim_result.rowcount != 1:
            # Another Partner won the claim while this transaction was preparing
            # the existing-lead route. Roll back every interim conversation change.
            db.rollback()
            fresh = db.execute(
                "SELECT client_conversation_id FROM website_inquiries WHERE id=?",
                (inquiry_id,),
            ).fetchone()
            return False, "This inquiry has already been claimed.", (fresh["client_conversation_id"] if fresh else None)
        _dismiss_inquiry_notifications(inquiry_id, except_user_id=_partner_user_id(owner_id))
        _notify_founders("INQUIRY_ROUTED", f"Inquiry routed to existing lead", f"{inquiry['company'] or inquiry['name']} stays with its current owner.", entity_type="conversation", entity_id=conversation_id)
        db.commit()
        if owner_id != partner_id:
            return False, "This contact already belongs to an existing RSF lead, so it was routed to that lead's owner.", conversation_id
        return True, "Inquiry linked to your existing lead.", conversation_id

    company_name = (inquiry["company"] or inquiry["name"] or "Website inquiry").strip()[:200]
    contact_name = (inquiry["name"] or company_name).strip()[:160]
    cur = db.execute(
        """INSERT INTO leads
           (owner_partner_id,company_name,company_norm,contact_name,contact_norm,email,email_norm,phone,phone_norm,
            website,website_domain,lead_source,summary_notes,status,lost_reason,demo_at,registered_at,last_activity_at,created_by_user_id)
           VALUES (?,?,?,?,?,?,?,'','','','','RSF Website','','NEW','',NULL,?,?,?)""",
        (partner_id, company_name, normalize_text(company_name), contact_name, normalize_text(contact_name),
         inquiry["email"], normalize_email(inquiry["email"]), now, now, actor_user_id),
    )
    lead_id = int(cur.lastrowid)
    conversation_id = int(inquiry["client_conversation_id"])
    updated = db.execute(
        """UPDATE website_inquiries SET status='CLAIMED',claimed_by_partner_id=?,claimed_at=?,lead_id=?,updated_at=?
           WHERE id=? AND status='UNCLAIMED' AND claimed_by_partner_id IS NULL""",
        (partner_id, now, lead_id, now, inquiry_id),
    )
    if updated.rowcount != 1:
        db.rollback()
        return False, "This inquiry has already been claimed.", None
    db.execute(
        """UPDATE client_conversations SET owner_partner_id=?,lead_id=?,updated_at=?,first_response_due_at=?
           WHERE id=?""",
        (partner_id, lead_id, now, _sla_due(now), conversation_id),
    )
    db.execute(
        """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
           VALUES (?,'INQUIRY_CLAIMED','lead',?,'Website inquiry claimed and converted to a lead.',?,?)""",
        (actor_user_id, lead_id, '{"inquiry_id":%d}' % inquiry_id, now),
    )
    owner_user_id = _partner_user_id(partner_id)
    _dismiss_inquiry_notifications(inquiry_id, except_user_id=owner_user_id)
    _notify(owner_user_id, "INQUIRY_CLAIMED", f"You claimed {company_name}", "Reply to the client within the response target.", entity_type="conversation", entity_id=conversation_id)
    _notify_founders("INQUIRY_CLAIMED", f"{company_name} was claimed", f"Claimed by {partner['full_name']}.", entity_type="conversation", entity_id=conversation_id)
    db.commit()
    return True, "Inquiry claimed. It is now your lead.", conversation_id


def assign_inquiry(inquiry_id: int, partner_id: int, actor_user_id: int) -> tuple[bool, str, int | None]:
    return claim_inquiry(inquiry_id, partner_id, actor_user_id)


def send_client_email(conversation_id: int, actor_user_id: int, body: str, attachments=None) -> int:
    if not email_send_configured():
        raise RuntimeError("Email sending is not set up yet.")
    db = get_db()
    conv = db.execute("SELECT * FROM client_conversations WHERE id=?", (conversation_id,)).fetchone()
    if not conv:
        raise ValueError("Client conversation not found.")
    body = (body or "").strip()
    prepared = _prepare_outbound_attachments(attachments)
    if not body and not prepared:
        raise ValueError("Write a reply or attach a file first.")
    if len(body) > 20000:
        raise ValueError("Reply is too long.")

    sender = current_app.config["RSF_EMAIL_ADDRESS"]
    display = current_app.config.get("RSF_EMAIL_NAME", "Realty Systems Foundry")
    subject = conv["subject"] or "Your Realty Systems Foundry inquiry"
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    last_msg = db.execute(
        """SELECT external_message_id FROM client_messages
           WHERE conversation_id=? AND external_message_id<>'' ORDER BY id DESC LIMIT 1""", (conversation_id,)
    ).fetchone()
    reply_to_id = last_msg["external_message_id"] if last_msg else ""
    message_id = make_msgid(domain=(sender.split("@", 1)[1] if "@" in sender else None))
    now = utcnow_iso()

    # Save the outgoing message before contacting SMTP. If the network succeeds but
    # a later database step fails, RSF still has a durable message record to review.
    cur = db.execute(
        """INSERT INTO client_messages
           (conversation_id,direction,channel,journey_source,sender_email,recipient_email,subject,body,sent_by_user_id,external_message_id,in_reply_to,created_at,delivery_status,delivery_error)
           VALUES (?,'OUTBOUND','EMAIL',?,?,?,?,?,?,?,?,?,'PENDING','')""",
        (
            conversation_id,
            "INBOUND" if conv["inquiry_id"] else ("OUTBOUND" if conv["prospect_id"] else ""),
            sender,
            conv["client_email"],
            subject,
            body,
            actor_user_id,
            message_id,
            reply_to_id,
            now,
        ),
    )
    message_row_id = int(cur.lastrowid)
    for name, mime_type, data in prepared:
        stored_id = _store_attachment_bytes(message_row_id, name, data, mime_type)
        if stored_id is None:
            db.rollback()
            raise ValueError(f"Attachment could not be saved safely: {name}")
    db.commit()

    msg = EmailMessage()
    msg["From"] = formataddr((display, sender))
    msg["To"] = conv["client_email"]
    msg["Reply-To"] = sender
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    if reply_to_id:
        msg["In-Reply-To"] = reply_to_id
        msg["References"] = reply_to_id
    msg.set_content(body or "Please see the attached file(s).")
    for name, mime_type, data in prepared:
        maintype, subtype = (mime_type.split("/", 1) + ["octet-stream"])[:2]
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

    host = current_app.config["SMTP_HOST"]
    port = int(current_app.config.get("SMTP_PORT", 465))
    username = current_app.config["SMTP_USERNAME"]
    password = current_app.config["SMTP_PASSWORD"]
    use_ssl = bool(current_app.config.get("SMTP_USE_SSL", True))
    use_tls = bool(current_app.config.get("SMTP_USE_TLS", False))
    try:
        server = smtplib.SMTP_SSL(host, port, timeout=20) if use_ssl else smtplib.SMTP(host, port, timeout=20)
        try:
            server.ehlo()
            if use_tls and not use_ssl:
                server.starttls()
                server.ehlo()
            server.login(username, password)
            refused = server.send_message(msg)
            if refused:
                raise RuntimeError("The mail server refused the client email address.")
        finally:
            try:
                server.quit()
            except Exception:
                pass
    except Exception as exc:
        try:
            db.execute(
                "UPDATE client_messages SET delivery_status='FAILED',delivery_error=? WHERE id=?",
                (str(exc)[:500], message_row_id),
            )
            db.commit()
        except Exception:
            db.rollback()
        raise RuntimeError("RSF could not send that email. Check the email setup and try again.") from exc

    # Save SMTP success immediately. Later CRM updates are a separate transaction.
    sent_at = utcnow_iso()
    try:
        db.execute(
            "UPDATE client_messages SET delivery_status='SENT',delivery_error='',created_at=? WHERE id=?",
            (sent_at, message_row_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        current_app.logger.exception("Email was sent but RSF could not update delivery status for message %s", message_row_id)
        # The pre-send PENDING record remains as proof that the send was attempted.
        raise RuntimeError("The email was sent, but RSF could not finish saving its status. Check the message history before sending again.")

    try:
        db.execute(
            """UPDATE client_conversations SET updated_at=?,subject=?,last_outbound_message_at=?,
               first_responded_at=COALESCE(first_responded_at,?) WHERE id=?""",
            (sent_at, subject.removeprefix("Re: "), sent_at, sent_at, conversation_id),
        )
        if conv["lead_id"]:
            lead = db.execute("SELECT status FROM leads WHERE id=?", (conv["lead_id"],)).fetchone()
            if lead and lead["status"] == "NEW":
                db.execute("UPDATE leads SET status='CONTACTED',last_activity_at=? WHERE id=?", (sent_at, conv["lead_id"]))
                db.execute(
                    """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
                       VALUES (?,'LEAD_STATUS_CHANGED','lead',?,'Lead moved from New to Contacted after the first client reply.','{"from":"NEW","to":"CONTACTED"}',?)""",
                    (actor_user_id, conv["lead_id"], sent_at),
                )
            else:
                db.execute("UPDATE leads SET last_activity_at=? WHERE id=?", (sent_at, conv["lead_id"]))
            db.execute(
                """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
                   VALUES (?,'CLIENT_EMAIL_SENT','lead',?,'Client email sent from RSF.',?,?)""",
                (actor_user_id, conv["lead_id"], '{"conversation_id":%d}' % conversation_id, sent_at),
            )
        db.execute(
            """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
               WHERE user_id=? AND entity_type='conversation' AND entity_id=?""",
            (sent_at, actor_user_id, conversation_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        current_app.logger.exception("Email was sent but post-send CRM updates failed for message %s", message_row_id)
        # Do not raise here: delivery and its durable SENT record are already confirmed.
    return message_row_id


def _decode_subject(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))[:240]
    except Exception:
        return value[:240]


def _match_conversation(message, sender_email: str):
    db = get_db()
    ids: list[str] = []
    for header in (message.get("In-Reply-To", ""), message.get("References", "")):
        ids.extend(part.strip() for part in header.split() if part.strip().startswith("<"))
    for mid in reversed(ids):
        row = db.execute(
            """SELECT c.* FROM client_messages m JOIN client_conversations c ON c.id=m.conversation_id
               WHERE m.external_message_id=? LIMIT 1""", (mid,)
        ).fetchone()
        if row:
            return row
    # Safe fallback only when exactly one active conversation uses this email.
    rows = db.execute(
        "SELECT * FROM client_conversations WHERE lower(client_email)=lower(?) AND status='ACTIVE' ORDER BY updated_at DESC LIMIT 2",
        (sender_email,),
    ).fetchall()
    return rows[0] if len(rows) == 1 else None


def _create_direct_email_inquiry(sender_name: str, sender_email: str, subject: str, body: str, external_id: str, attachments=None) -> int:
    record = {
        "name": sender_name or sender_email.split("@", 1)[0], "email": sender_email, "company": "",
        "message": body, "source_type": "email", "source_title": "Direct email", "source_action": "email",
    }
    inquiry_id = create_public_inquiry(record)
    db = get_db()
    inquiry = db.execute("SELECT client_conversation_id FROM website_inquiries WHERE id=?", (inquiry_id,)).fetchone()
    conv_id = int(inquiry["client_conversation_id"])
    first = db.execute("SELECT id FROM client_messages WHERE conversation_id=? ORDER BY id DESC LIMIT 1", (conv_id,)).fetchone()
    db.execute(
        "UPDATE client_messages SET channel='EMAIL',subject=?,external_message_id=?,delivery_status='RECEIVED' WHERE id=?",
        (subject, external_id, first["id"]),
    )
    for name, mime_type, data in list(attachments or []):
        _store_attachment_bytes(int(first["id"]), name, data, mime_type)
    db.execute("UPDATE client_conversations SET subject=?,last_client_message_at=? WHERE id=?", (subject, utcnow_iso(), conv_id))
    db.commit()
    return conv_id


def _mark_bounce_if_applicable(message, sender_email: str, subject: str) -> bool:
    local = sender_email.split("@", 1)[0].lower() if "@" in sender_email else sender_email.lower()
    if local not in {"mailer-daemon", "postmaster"} and "undeliver" not in subject.lower() and "delivery status" not in subject.lower():
        return False
    db = get_db()
    candidates: list[str] = []
    for header in (message.get("In-Reply-To", ""), message.get("References", ""), message.get("Original-Message-ID", "")):
        candidates.extend(part.strip() for part in str(header).split() if part.strip().startswith("<"))
    row = None
    for mid in reversed(candidates):
        row = db.execute(
            """SELECT m.id,m.conversation_id,c.owner_partner_id,c.lead_id,c.company,c.client_name
               FROM client_messages m JOIN client_conversations c ON c.id=m.conversation_id
               WHERE m.external_message_id=? AND m.direction='OUTBOUND' LIMIT 1""", (mid,)
        ).fetchone()
        if row:
            break
    if not row:
        return False
    now = utcnow_iso()
    db.execute("UPDATE client_messages SET delivery_status='BOUNCED',delivery_error=? WHERE id=?", (subject[:500], row["id"]))
    owner_user_id = _partner_user_id(row["owner_partner_id"])
    title = f"Email bounced: {row['company'] or row['client_name']}"
    _notify(owner_user_id, "EMAIL_BOUNCED", title, "The client email could not be delivered.", entity_type="conversation", entity_id=row["conversation_id"])
    _notify_founders("EMAIL_BOUNCED", title, "The client email could not be delivered.", entity_type="conversation", entity_id=row["conversation_id"])
    if row["lead_id"]:
        db.execute(
            """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
               VALUES (NULL,'CLIENT_EMAIL_BOUNCED','lead',?,'Client email bounced.','{}',?)""", (row["lead_id"], now)
        )
    db.commit()
    return True


def sync_inbound_email(limit: int = 40) -> dict[str, int]:
    if not email_receive_configured():
        raise RuntimeError("Email receiving is not set up yet.")
    host = current_app.config["IMAP_HOST"]
    port = int(current_app.config.get("IMAP_PORT", 993))
    username = current_app.config["IMAP_USERNAME"]
    password = current_app.config["IMAP_PASSWORD"]
    mailbox = current_app.config.get("IMAP_MAILBOX", "INBOX")
    use_ssl = bool(current_app.config.get("IMAP_USE_SSL", True))
    client = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    imported = 0
    skipped = 0
    bounced = 0
    try:
        client.login(username, password)
        typ, _ = client.select(mailbox)
        if typ != "OK":
            raise RuntimeError("Could not open the RSF mailbox.")
        typ, data = client.search(None, "UNSEEN")
        if typ != "OK":
            return {"imported": 0, "skipped": 0, "bounced": 0}
        message_ids = (data[0].split() if data and data[0] else [])[-max(1, min(limit, 200)):]
        for imap_id in message_ids:
            typ, raw = client.fetch(imap_id, "(RFC822)")
            if typ != "OK" or not raw or not isinstance(raw[0], tuple):
                skipped += 1
                continue
            msg = email.message_from_bytes(raw[0][1], policy=email.policy.default)
            ext_id = (msg.get("Message-ID") or "").strip()
            db = get_db()
            if ext_id and db.execute("SELECT 1 FROM client_messages WHERE external_message_id=?", (ext_id,)).fetchone():
                client.store(imap_id, "+FLAGS", "\\Seen")
                skipped += 1
                continue
            sender_name, sender_email = parseaddr(msg.get("From", ""))
            sender_email = normalize_email(sender_email)
            rsf_email = normalize_email(current_app.config.get("RSF_EMAIL_ADDRESS", ""))
            subject = _decode_subject(msg.get("Subject"))
            if sender_email and _mark_bounce_if_applicable(msg, sender_email, subject):
                client.store(imap_id, "+FLAGS", "\\Seen")
                bounced += 1
                continue
            if not sender_email or sender_email == rsf_email:
                client.store(imap_id, "+FLAGS", "\\Seen")
                skipped += 1
                continue
            body = _text_part(msg)[:20000]
            attachments = _extract_inbound_attachments(msg)
            conv = _match_conversation(msg, sender_email)
            if conv and conv["owner_partner_id"] is not None and not _active_partner(int(conv["owner_partner_id"])):
                conv = None
            if conv:
                now = utcnow_iso()
                cur = db.execute(
                    """INSERT INTO client_messages
                       (conversation_id,direction,channel,journey_source,sender_email,recipient_email,subject,body,external_message_id,in_reply_to,created_at,delivery_status,delivery_error)
                       VALUES (?,'INBOUND','EMAIL',?,?,?,?,?,?,?,?,'RECEIVED','')""",
                    (
                        conv["id"],
                        "INBOUND" if conv["inquiry_id"] else ("OUTBOUND" if conv["prospect_id"] else ""),
                        sender_email,
                        rsf_email,
                        subject,
                        body,
                        ext_id,
                        (msg.get("In-Reply-To") or "")[:500],
                        now,
                    ),
                )
                message_id = int(cur.lastrowid)
                for name, mime_type, data_bytes in attachments:
                    _store_attachment_bytes(message_id, name, data_bytes, mime_type)
                db.execute(
                    "UPDATE client_conversations SET updated_at=?,last_client_message_at=? WHERE id=?",
                    (now, now, conv["id"]),
                )
                owner_user_id = _partner_user_id(conv["owner_partner_id"])
                label = conv["company"] or conv["client_name"]
                _notify(owner_user_id, "CLIENT_REPLY", f"New reply from {label}", subject or "Client replied to RSF.", entity_type="conversation", entity_id=conv["id"])
                _notify_founders("CLIENT_REPLY", f"New reply from {label}", subject or "Client replied to RSF.", entity_type="conversation", entity_id=conv["id"])
                if conv["lead_id"]:
                    db.execute("UPDATE leads SET last_activity_at=? WHERE id=?", (now, conv["lead_id"]))
                    db.execute(
                        """INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at)
                           VALUES (NULL,'CLIENT_EMAIL_RECEIVED','lead',?,'Client email reply received.','{}',?)""",
                        (conv["lead_id"], now),
                    )
                db.commit()
            else:
                _create_direct_email_inquiry(sender_name, sender_email, subject, body, ext_id, attachments)
            client.store(imap_id, "+FLAGS", "\\Seen")
            imported += 1
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return {"imported": imported, "skipped": skipped, "bounced": bounced}
