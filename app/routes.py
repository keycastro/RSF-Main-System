from __future__ import annotations

import html as html_lib
import json
import os
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

import pymupdf
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, Response, abort, current_app, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
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
from .credential_vault import current_password as vault_current_password, store_password as vault_store_password
from .record_ops import (
    RECORD_DELETE_PROTECTED_STATUSES,
    build_master_records,
    find_master_record,
    find_matching_prospect,
    find_matching_website_inquiry,
)
from .services import (
    PARTNER_ALLOWED_STATUSES,
    PAYMENT_STATUSES,
    PIPELINE,
    RESOURCE_CATEGORIES,
    commission_amount,
    commission_change_for_revenue,
    create_commission_for_sale,
    duplicate_candidates,
    file_signature_matches,
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
    transfer_lead_ownership,
    validate_sale_amounts,
    utcnow_iso,
)

bp = Blueprint("main", __name__)


def local_now_input() -> str:
    return datetime.now().astimezone().replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def today_str() -> str:
    return date.today().isoformat()


def partner_scope_id() -> int | None:
    return g.partner["id"] if g.user and g.user["role"] == "partner" and g.partner else None


PROSPECT_STATUS_LABELS = {
    "NOT_CONTACTED": "Not Contacted",
    "NO_ANSWER": "No Answer",
    "REJECTED": "Rejected",
    "DEAL": "Deal",
    "DEMO": "Demo",
    "PROPOSAL": "Proposal",
    "DECISION": "Decision",
    "WON": "Won",
    "LOST": "Lost",
}
# The ordered status map is canonical. Anything from DEAL onward is Deal-side,
# so future stages inserted after DEAL inherit Deal lifecycle behavior automatically.
PROSPECT_STATUS_CODES = tuple(PROSPECT_STATUS_LABELS)
DEAL_PIPELINE_START_INDEX = PROSPECT_STATUS_CODES.index("DEAL")
DEAL_PRE_STATUS_STATUSES = PROSPECT_STATUS_CODES[:DEAL_PIPELINE_START_INDEX]
DEAL_ACTIVE_STATUSES = PROSPECT_STATUS_CODES[DEAL_PIPELINE_START_INDEX:]

CARD_LAYOUT_SPECS = {
    "prospects": {
        "zones": ("header", "summary", "source", "other"),
        "fields": {
            "business_type", "status", "budget", "post_date", "city_country",
            "platform_wanted", "problem", "system_wanted", "notes_after_conversation",
            "post_link", "website", "company", "client_name", "email",
            "contact_number", "whatsapp_number", "email_conversation", "contact_attempt", "followup_date",
            "price", "developer", "demo_schedule", "next_step", "google_meet",
        },
    },
    "inquiries": {
        "zones": ("header", "source", "deal"),
        "fields": {
            "client_name", "status", "email", "contact_number", "whatsapp_number", "company", "request",
            "message", "notes_after_conversation", "email_conversation", "followup_date",
            "price", "developer", "city_country", "demo_schedule", "next_step", "google_meet",
        },
    },
    "deals": {
        "zones": ("header", "deal", "outbound", "inbound"),
        "fields": {
            "client_name", "status", "followup_date", "email", "price", "developer",
            "contact_number", "whatsapp_number", "city_country", "demo_schedule", "next_step",
            "notes_after_conversation", "google_meet", "email_conversation",
            "outbound_business_type", "outbound_budget", "outbound_post_date",
            "outbound_platform_wanted", "outbound_problem", "outbound_system_wanted",
            "outbound_post_link", "outbound_website", "outbound_company",
            "outbound_contact_attempt", "outbound_added_date", "inbound_company",
            "inbound_request", "inbound_message", "inbound_received_date",
        },
    },
}


def _card_layout_setting_key(page_name: str) -> str:
    return f"card_layout_{page_name}_v1"


def _card_layout_preference(db, page_name: str) -> dict[str, list[str]]:
    spec = CARD_LAYOUT_SPECS.get(page_name)
    if not spec:
        return {}
    row = db.execute(
        "SELECT value FROM settings WHERE key=? LIMIT 1",
        (_card_layout_setting_key(page_name),),
    ).fetchone()
    if not row:
        return {}
    try:
        payload = json.loads(row["value"] or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    allowed_fields = set(spec["fields"])
    cleaned: dict[str, list[str]] = {}
    seen: set[str] = set()
    for zone in spec["zones"]:
        values = payload.get(zone, [])
        if not isinstance(values, list):
            continue
        items: list[str] = []
        for value in values:
            key = str(value or "").strip()
            if key in allowed_fields and key not in seen:
                items.append(key)
                seen.add(key)
        if items:
            cleaned[zone] = items
    return cleaned


DEAL_DOCUMENT_MAX_FILE_BYTES = 30 * 1024 * 1024
DEAL_DOCUMENT_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
    ".zip": "application/zip",
}


def _deal_document_file_info(storage) -> dict:
    original_name = secure_filename(storage.filename or "") if storage is not None else ""
    if not original_name:
        raise ValueError("Choose a file first.")

    suffix = Path(original_name).suffix.lower()
    mime_type = DEAL_DOCUMENT_FILE_TYPES.get(suffix)
    if not mime_type:
        raise ValueError("Supported files: PDF, DOCX, XLSX, CSV, PNG, JPG/JPEG, TXT, ZIP.")

    try:
        storage.stream.seek(0, 2)
        size_bytes = int(storage.stream.tell())
        storage.stream.seek(0)
        header = storage.stream.read(4096)
        storage.stream.seek(0)
    except (AttributeError, OSError, ValueError):
        size_bytes = int(storage.content_length or 0)
        header = b""

    if size_bytes <= 0:
        raise ValueError("That file is empty.")
    if size_bytes > DEAL_DOCUMENT_MAX_FILE_BYTES:
        raise ValueError("Each Deal file must be 30 MB or smaller.")
    if not file_signature_matches(suffix, header):
        raise ValueError("The file content does not match its file type.")

    return {
        "storage": storage,
        "original_name": original_name[:180],
        "suffix": suffix,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
    }


def _deal_document_download_name(row) -> str:
    suffix = Path(row["original_name"] or "").suffix.lower()
    base = secure_filename(row["display_name"] or "") or Path(row["original_name"] or "document").stem
    if suffix and not base.lower().endswith(suffix):
        return (base + suffix)[:220]
    return base[:220]


def _deal_document_preview_shell(title: str, body_html: str) -> Response:
    safe_title = html_lib.escape(title or "Deal file")
    content = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title><style>
html,body{{margin:0;min-height:100%;background:#f5f7f6;color:#1b322b;font:14px/1.5 Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{box-sizing:border-box;max-width:1100px;margin:0 auto;padding:24px}}.preview-card{{background:#fff;border:1px solid #dfe7e3;border-radius:12px;padding:20px;box-shadow:0 4px 16px rgba(25,55,46,.06)}}
h1{{margin:0 0 16px;font-size:18px;line-height:1.3}}h2{{margin:22px 0 10px;font-size:15px}}pre{{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace}}
table{{width:100%;border-collapse:collapse;font-size:12px}}td{{border:1px solid #dfe7e3;padding:7px 8px;vertical-align:top;overflow-wrap:anywhere}}.archive{{display:grid;gap:7px}}
.archive-row{{display:flex;justify-content:space-between;gap:18px;padding:8px 10px;border:1px solid #e3eae7;border-radius:8px;background:#fbfdfc}}.muted{{color:#6f7f79}}.empty{{padding:20px;text-align:center;color:#6f7f79}}
.image-preview{{display:flex;justify-content:center;min-width:0}}.image-preview img{{display:block;max-width:100%;height:auto}}
.pdf-pages{{display:grid;gap:18px}}.pdf-page{{display:block;width:100%;height:auto;margin:0 auto;background:#fff;box-shadow:0 2px 10px rgba(0,0,0,.12)}}
</style></head><body><main><section class="preview-card"><h1>{safe_title}</h1>{body_html}</section></main></body></html>"""
    response = Response(content, mimetype="text/html")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
    response.headers["Cache-Control"] = "no-store, private, max-age=0"
    return response


def _zip_read_limited(archive: zipfile.ZipFile, name: str, limit: int = 8 * 1024 * 1024) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > limit:
        raise ValueError("Preview content is too large.")
    with archive.open(info, "r") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Preview content is too large.")
    return data


def _deal_document_docx_preview(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml_data = _zip_read_limited(archive, "word/document.xml")
    root = ET.fromstring(xml_data)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns)[:600]:
        value = "".join((node.text or "") for node in paragraph.findall(".//w:t", ns)).strip()
        if value:
            paragraphs.append(value)
    if not paragraphs:
        return '<div class="empty">No readable text found in this DOCX file.</div>'
    joined = (chr(10) * 2).join(paragraphs)[:120000]
    return f"<pre>{html_lib.escape(joined)}</pre>"


def _deal_document_xlsx_preview(data: bytes) -> str:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(BytesIO(data)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(_zip_read_limited(archive, "xl/sharedStrings.xml"))
            for item in root.findall(".//m:si", ns):
                shared.append("".join((node.text or "") for node in item.findall(".//m:t", ns)))
        sheet_names = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))[:8]
        if not sheet_names:
            return '<div class="empty">No worksheet data found in this XLSX file.</div>'
        sections = []
        for index, sheet_name in enumerate(sheet_names, start=1):
            root = ET.fromstring(_zip_read_limited(archive, sheet_name))
            rows_html = []
            for row in root.findall(".//m:sheetData/m:row", ns)[:250]:
                cells = []
                for cell in row.findall("m:c", ns)[:60]:
                    cell_type = cell.attrib.get("t", "")
                    value = ""
                    if cell_type == "inlineStr":
                        value = "".join((node.text or "") for node in cell.findall(".//m:t", ns))
                    else:
                        node = cell.find("m:v", ns)
                        value = node.text if node is not None and node.text is not None else ""
                        if cell_type == "s" and value.isdigit():
                            pos = int(value)
                            value = shared[pos] if 0 <= pos < len(shared) else value
                    cells.append(f"<td>{html_lib.escape(value)}</td>")
                if cells:
                    rows_html.append("<tr>" + "".join(cells) + "</tr>")
            table = "<table>" + "".join(rows_html) + "</table>" if rows_html else '<div class="empty">No visible cells.</div>'
            sections.append(f"<h2>Sheet {index}</h2>{table}")
        return "".join(sections)


def _deal_document_zip_preview(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        items = archive.infolist()
    if not items:
        return '<div class="empty">This ZIP archive is empty.</div>'
    rows = []
    for item in items[:500]:
        rows.append('<div class="archive-row"><span>' + html_lib.escape(item.filename) + '</span><span class="muted">' + html_lib.escape(f"{item.file_size:,} bytes") + '</span></div>')
    if len(items) > 500:
        rows.append(f'<p class="muted">Showing first 500 of {len(items)} archive items.</p>')
    return '<div class="archive">' + "".join(rows) + "</div>"


def _deal_document_html_preview(row, *, deal_id: int, document_id: int) -> Response:
    data = bytes(row["data_blob"] or b"")
    suffix = Path(row["original_name"] or "").suffix.lower()
    title = row["display_name"] or row["original_name"] or "Deal file"
    try:
        if suffix in {".png", ".jpg", ".jpeg"}:
            asset_url = url_for(
                "main.deal_document_preview_asset",
                deal_id=deal_id,
                document_id=document_id,
            )
            body = (
                '<div class="image-preview"><img alt="' +
                html_lib.escape(title, quote=True) +
                '" src="' + html_lib.escape(asset_url, quote=True) + '"></div>'
            )
        elif suffix == ".docx":
            body = _deal_document_docx_preview(data)
        elif suffix == ".xlsx":
            body = _deal_document_xlsx_preview(data)
        elif suffix == ".zip":
            body = _deal_document_zip_preview(data)
        elif suffix in {".txt", ".csv"}:
            value = data[:2 * 1024 * 1024].decode("utf-8-sig", errors="replace")
            body = f"<pre>{html_lib.escape(value)}</pre>"
        else:
            body = '<div class="empty">Preview is not available for this file.</div>'
    except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError):
        body = '<div class="empty">This file could not be rendered safely. Use Download to open the original file.</div>'
    return _deal_document_preview_shell(title, body)


def _normalize_prospect_name(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def _shared_opportunity_status(status: str) -> bool:
    return (status or "").strip().upper() not in ("REJECTED", "WON", "LOST")


def _sync_deal_source_statuses(db, deal_id: int, status: str, now: str) -> None:
    deal = db.execute(
        "SELECT prospect_id,website_inquiry_id FROM deals WHERE id=?",
        (deal_id,),
    ).fetchone()
    if not deal:
        return
    if deal["prospect_id"] is not None:
        db.execute(
            "UPDATE prospects SET status=?,updated_at=? WHERE id=?",
            (status, now, deal["prospect_id"]),
        )
    if deal["website_inquiry_id"] is not None:
        db.execute(
            "UPDATE website_inquiries SET workflow_status=?,updated_at=? WHERE id=?",
            (status, now, deal["website_inquiry_id"]),
        )


def _mark_deal_became(db, deal_id: int, now: str) -> None:
    db.execute(
        """UPDATE deals
           SET became_deal_at=CASE WHEN trim(COALESCE(became_deal_at,''))='' THEN ? ELSE became_deal_at END,
               updated_at=?
           WHERE id=?""",
        (now, now, deal_id),
    )


def _merge_provisional_deal_into(db, source_deal_id: int, target_deal_id: int, now: str) -> int:
    if source_deal_id == target_deal_id:
        return target_deal_id
    source = db.execute("SELECT * FROM deals WHERE id=?", (source_deal_id,)).fetchone()
    target = db.execute("SELECT * FROM deals WHERE id=?", (target_deal_id,)).fetchone()
    if not source or not target:
        return target_deal_id

    db.execute("UPDATE deal_documents SET deal_id=? WHERE deal_id=?", (target_deal_id, source_deal_id))
    db.execute("UPDATE communication_notes SET deal_id=? WHERE deal_id=?", (target_deal_id, source_deal_id))
    db.execute("UPDATE whatsapp_messages SET deal_id=? WHERE deal_id=?", (target_deal_id, source_deal_id))
    db.execute("UPDATE manual_client_calls SET deal_id=? WHERE deal_id=?", (target_deal_id, source_deal_id))

    fill_fields = [
        "contact_person","location","demo_date","demo_time","demo_timezone","demo_timezone_location",
        "google_calendar_event_id","google_calendar_html_url","google_meet_url","google_calendar_sync_error",
        "google_calendar_synced_at","followup_date","next_step","price","developer","contact_number","whatsapp_number","email",
        "notes_after_conversation","became_deal_at",
    ]
    updates = []
    params = []
    for field in fill_fields:
        source_value = source[field] if field in source.keys() else ""
        target_value = target[field] if field in target.keys() else ""
        if (not str(target_value or "").strip()) and str(source_value or "").strip():
            updates.append(f"{field}=?")
            params.append(source_value)

    prospect_id = target["prospect_id"] or source["prospect_id"]
    inquiry_id = target["website_inquiry_id"] or source["website_inquiry_id"]
    db.execute("DELETE FROM deals WHERE id=?", (source_deal_id,))
    updates.extend(["prospect_id=?", "website_inquiry_id=?", "updated_at=?"])
    params.extend([prospect_id, inquiry_id, now, target_deal_id])
    db.execute(f"UPDATE deals SET {','.join(updates)} WHERE id=?", params)
    return target_deal_id


def _reconcile_deal_sources_on_activation(db, deal_id: int, now: str) -> int:
    deal = db.execute("SELECT prospect_id,website_inquiry_id FROM deals WHERE id=?", (deal_id,)).fetchone()
    if not deal:
        return deal_id

    if deal["prospect_id"] is not None and deal["website_inquiry_id"] is None:
        prospect = db.execute(
            "SELECT name,contact,email,phone FROM prospects WHERE id=?",
            (deal["prospect_id"],),
        ).fetchone()
        if prospect:
            match = find_matching_website_inquiry(
                db,
                {
                    "company": prospect["name"],
                    "contact_name": prospect["contact"],
                    "email": prospect["email"],
                    "phone": prospect["phone"],
                },
            )
            if match and (match["workflow_status"] or "").strip().upper() in DEAL_ACTIVE_STATUSES:
                other = db.execute(
                    "SELECT id FROM deals WHERE website_inquiry_id=? LIMIT 1",
                    (match["id"],),
                ).fetchone()
                if other and int(other["id"]) != deal_id:
                    return _merge_provisional_deal_into(db, deal_id, int(other["id"]), now)
                db.execute(
                    "UPDATE deals SET website_inquiry_id=?,updated_at=? WHERE id=?",
                    (match["id"], now, deal_id),
                )

    if deal["website_inquiry_id"] is not None and deal["prospect_id"] is None:
        inquiry = db.execute(
            "SELECT name,email,phone,company FROM website_inquiries WHERE id=?",
            (deal["website_inquiry_id"],),
        ).fetchone()
        if inquiry:
            match = find_matching_prospect(
                db,
                {
                    "company": inquiry["company"],
                    "contact_name": inquiry["name"],
                    "email": inquiry["email"],
                    "phone": inquiry["phone"],
                },
            )
            if match and (match["status"] or "").strip().upper() in DEAL_ACTIVE_STATUSES:
                other = db.execute(
                    "SELECT id FROM deals WHERE prospect_id=? LIMIT 1",
                    (match["id"],),
                ).fetchone()
                if other and int(other["id"]) != deal_id:
                    return _merge_provisional_deal_into(db, deal_id, int(other["id"]), now)
                db.execute(
                    "UPDATE deals SET prospect_id=?,updated_at=? WHERE id=?",
                    (match["id"], now, deal_id),
                )
    return deal_id


def _ensure_deal_for_prospect(db, prospect_id: int, created_by_user_id: int, now: str, *, allow_merge: bool = True) -> tuple[int, bool]:
    existing = db.execute("SELECT id FROM deals WHERE prospect_id=? LIMIT 1", (prospect_id,)).fetchone()
    if existing:
        return int(existing["id"]), False

    prospect = db.execute(
        """SELECT id,name,contact,email,phone,location,status,notes_after_conversation
           FROM prospects WHERE id=?""",
        (prospect_id,),
    ).fetchone()
    if not prospect:
        raise ValueError("Prospect not found.")

    matched_inquiry = None
    if allow_merge:
        matched_inquiry = find_matching_website_inquiry(
            db,
            {
                "company": prospect["name"],
                "contact_name": prospect["contact"],
                "email": prospect["email"],
                "phone": prospect["phone"],
            },
        )
        if matched_inquiry and not _shared_opportunity_status(matched_inquiry["workflow_status"]):
            matched_inquiry = None

    if matched_inquiry:
        inquiry_deal = db.execute(
            "SELECT id,prospect_id FROM deals WHERE website_inquiry_id=? LIMIT 1",
            (matched_inquiry["id"],),
        ).fetchone()
        if inquiry_deal and inquiry_deal["prospect_id"] is None:
            db.execute(
                """UPDATE deals
                   SET prospect_id=?,
                       contact_number=CASE WHEN trim(contact_number)='' THEN ? ELSE contact_number END,
                       email=CASE WHEN trim(email)='' THEN ? ELSE email END,
                       updated_at=?
                   WHERE id=?""",
                (
                    prospect_id,
                    (prospect["phone"] or "")[:120],
                    (prospect["email"] or "")[:320],
                    now,
                    inquiry_deal["id"],
                ),
            )
            log_activity(
                "DEAL_SOURCE_MERGED",
                "deal",
                int(inquiry_deal["id"]),
                "Research Prospect linked to the existing Website Deal.",
                {"prospect_id": prospect_id, "website_inquiry_id": int(matched_inquiry["id"])},
            )
            return int(inquiry_deal["id"]), False

    source_is_deal = (prospect["status"] or "").strip().upper() in DEAL_ACTIVE_STATUSES
    db.execute(
        """INSERT OR IGNORE INTO deals(
               prospect_id,website_inquiry_id,status,demo_date,followup_date,next_step,price,
               contact_number,email,notes_after_conversation,became_deal_at,
               created_by_user_id,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            prospect_id,
            int(matched_inquiry["id"]) if matched_inquiry else None,
            "DEAL",
            "",
            "",
            "",
            "",
            (prospect["phone"] or "").strip()[:120],
            (prospect["email"] or "").strip()[:320],
            (prospect["notes_after_conversation"] or "").strip()[:3000],
            now if source_is_deal else "",
            created_by_user_id,
            now,
            now,
        ),
    )
    deal = db.execute("SELECT id FROM deals WHERE prospect_id=? LIMIT 1", (prospect_id,)).fetchone()
    if not deal:
        raise RuntimeError("Deal could not be created.")
    deal_id = int(deal["id"])
    if source_is_deal:
        log_activity(
            "DEAL_CREATED",
            "deal",
            deal_id,
            "Deal created automatically from Prospect Status.",
            {
                "prospect_id": prospect_id,
                "website_inquiry_id": int(matched_inquiry["id"]) if matched_inquiry else None,
            },
        )
    return deal_id, True

def _ensure_deal_for_website_inquiry(db, inquiry_id: int, created_by_user_id: int, now: str, *, allow_merge: bool = True) -> tuple[int, bool]:
    existing = db.execute("SELECT id FROM deals WHERE website_inquiry_id=? LIMIT 1", (inquiry_id,)).fetchone()
    if existing:
        return int(existing["id"]), False

    inquiry = db.execute(
        """SELECT id,name,email,phone,company,workflow_status,notes_after_conversation
           FROM website_inquiries WHERE id=?""",
        (inquiry_id,),
    ).fetchone()
    if not inquiry:
        raise ValueError("Website Inquiry not found.")

    matched_prospect = None
    if allow_merge:
        matched_prospect = find_matching_prospect(
            db,
            {
                "company": inquiry["company"],
                "contact_name": inquiry["name"],
                "email": inquiry["email"],
                "phone": inquiry["phone"],
            },
        )
        if matched_prospect and not _shared_opportunity_status(matched_prospect["status"]):
            matched_prospect = None

    if matched_prospect:
        prospect_deal = db.execute(
            "SELECT id,website_inquiry_id FROM deals WHERE prospect_id=? LIMIT 1",
            (matched_prospect["id"],),
        ).fetchone()
        if prospect_deal and prospect_deal["website_inquiry_id"] is None:
            db.execute(
                """UPDATE deals
                   SET website_inquiry_id=?,
                       contact_number=CASE WHEN trim(contact_number)='' THEN ? ELSE contact_number END,
                       email=CASE WHEN trim(email)='' THEN ? ELSE email END,
                       updated_at=?
                   WHERE id=?""",
                (
                    inquiry_id,
                    (inquiry["phone"] or "")[:120],
                    (inquiry["email"] or "")[:320],
                    now,
                    prospect_deal["id"],
                ),
            )
            log_activity(
                "DEAL_SOURCE_MERGED",
                "deal",
                int(prospect_deal["id"]),
                "Website Inquiry linked to the existing Research Deal.",
                {"prospect_id": int(matched_prospect["id"]), "website_inquiry_id": inquiry_id},
            )
            return int(prospect_deal["id"]), False

    source_is_deal = (inquiry["workflow_status"] or "").strip().upper() in DEAL_ACTIVE_STATUSES
    db.execute(
        """INSERT OR IGNORE INTO deals(
               prospect_id,website_inquiry_id,contact_person,location,status,demo_date,followup_date,next_step,price,
               contact_number,email,notes_after_conversation,became_deal_at,
               created_by_user_id,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            int(matched_prospect["id"]) if matched_prospect else None,
            inquiry_id,
            (inquiry["name"] or "").strip()[:200].upper(),
            "",
            "DEAL",
            "",
            "",
            "",
            "",
            (inquiry["phone"] or "").strip()[:120],
            (inquiry["email"] or "").strip()[:320],
            (inquiry["notes_after_conversation"] or "").strip()[:3000],
            now if source_is_deal else "",
            created_by_user_id,
            now,
            now,
        ),
    )
    deal = db.execute("SELECT id FROM deals WHERE website_inquiry_id=? LIMIT 1", (inquiry_id,)).fetchone()
    if not deal:
        raise RuntimeError("Deal could not be created.")
    deal_id = int(deal["id"])
    if source_is_deal:
        log_activity(
            "DEAL_CREATED",
            "deal",
            deal_id,
            "Deal created automatically from Website Inquiry Status.",
            {
                "website_inquiry_id": inquiry_id,
                "prospect_id": int(matched_prospect["id"]) if matched_prospect else None,
            },
        )
    return deal_id, True



def _sync_calendar_for_activated_deal(db, deal_id: int) -> None:
    row = db.execute(
        """SELECT id,contact_person,email,demo_date,demo_time,demo_timezone,
                  google_calendar_event_id
           FROM deals WHERE id=?""",
        (deal_id,),
    ).fetchone()
    if not row or not row["demo_date"] or not row["demo_time"] or not row["demo_timezone"]:
        return

    from .calendar_ops import calendar_connected, create_or_update_deal_meeting
    if not calendar_connected():
        return

    try:
        result = create_or_update_deal_meeting(
            event_id=(row["google_calendar_event_id"] or "").strip(),
            client_name=(row["contact_person"] or "").strip(),
            client_email=(row["email"] or "").strip(),
            demo_date=(row["demo_date"] or "").strip(),
            demo_time=(row["demo_time"] or "").strip(),
            demo_timezone=(row["demo_timezone"] or "").strip(),
        )
        now = utcnow_iso()
        db.execute(
            """UPDATE deals
               SET google_calendar_event_id=?,google_calendar_html_url=?,google_meet_url=?,
                   google_calendar_sync_error='',google_calendar_synced_at=?,updated_at=?
               WHERE id=?""",
            (
                result["event_id"],
                result["html_link"],
                result["meet_url"],
                now,
                now,
                deal_id,
            ),
        )
        log_activity(
            "DEMO_MEETING_SYNCED",
            "deal",
            deal_id,
            "Deal demo synchronized to Google Calendar with Google Meet.",
            {
                "demo_date": row["demo_date"],
                "demo_time": row["demo_time"],
                "demo_timezone": row["demo_timezone"],
            },
        )
        db.commit()
    except Exception as exc:
        current_app.logger.exception("Google Calendar Deal activation sync failed")
        message = str(exc)[:500] or "Google Calendar sync failed."
        db.execute(
            "UPDATE deals SET google_calendar_sync_error=?,updated_at=? WHERE id=?",
            (message, utcnow_iso(), deal_id),
        )
        db.commit()


def _deal_card_support(db, deal_rows) -> dict:
    rows = list(deal_rows or [])
    deal_ids = [int(row["id"]) for row in rows]
    deal_documents: dict[int, list] = {}
    if deal_ids:
        placeholders = ",".join("?" for _ in deal_ids)
        document_rows = db.execute(
            f"""SELECT id,deal_id,document_type,display_name,original_name,mime_type,size_bytes,created_at
                FROM deal_documents
                WHERE deal_id IN ({placeholders})
                ORDER BY deal_id,created_at DESC,id DESC""",
            deal_ids,
        ).fetchall()
        for document in document_rows:
            deal_documents.setdefault(int(document["deal_id"]), []).append(document)

    from .calendar_ops import connection_status as calendar_connection_status, demo_time_display
    from .timezone_location import timezone_display_location
    return {
        "deal_documents": deal_documents,
        "calendar_status": calendar_connection_status(),
        "deal_demo_time_displays": {
            int(row["id"]): demo_time_display(
                row["demo_date"],
                row["demo_time"],
                row["demo_timezone"],
            )
            for row in rows
        },
        "deal_timezone_location_displays": {
            int(row["id"]): (
                (row["demo_timezone_location"] or "").strip()
                or timezone_display_location((row["demo_timezone"] or "").strip())
            )
            for row in rows
        },
    }


def _clean_account_name(value: str) -> str:
    return (value or "").strip()[:160]


def _account_name_in_use(db, name: str, exclude_user_id: int | None = None) -> bool:
    sql = "SELECT id FROM users WHERE active=1 AND lower(trim(full_name))=lower(trim(?))"
    params: list[object] = [name]
    if exclude_user_id is not None:
        sql += " AND id<>?"
        params.append(exclude_user_id)
    return db.execute(sql + " LIMIT 1", params).fetchone() is not None


def _new_internal_account_email(db) -> str:
    # Legacy database compatibility only. Workspace users never see or use this value.
    for _ in range(5):
        value = f"workspace-{uuid4().hex}@internal.invalid"
        if not db.execute("SELECT 1 FROM users WHERE lower(email)=lower(?) LIMIT 1", (value,)).fetchone():
            return value
    raise RuntimeError("Could not create an internal account key.")




def authorized_conversation_partner(partner_id: int):
    db = get_db()
    partner = db.execute(
        """SELECT p.*, COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') full_name,
                  u.role AS user_role,u.avatar_stored_name,u.active AS user_active
           FROM partners p LEFT JOIN users u ON u.id=p.user_id WHERE p.id=?""",
        (partner_id,),
    ).fetchone()
    if not partner:
        abort(404)
    if g.user["role"] == "partner":
        if not g.partner or g.partner["id"] != partner_id or partner["account_deleted_at"] or not partner["user_id"]:
            # Hide other or deleted Partner threads from Partners.
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
        if partner["user_id"]:
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
        header = storage.stream.read(4096)
        storage.stream.seek(0)
    except (AttributeError, OSError, ValueError):
        size = int(storage.content_length or 0)
        header = b""
    if size <= 0:
        raise ValueError("That file is empty.")
    if size > MESSAGE_MAX_FILE_BYTES:
        raise ValueError("Each file must be 15 MB or smaller.")
    if not file_signature_matches(suffix, header):
        raise ValueError("The file content does not match its file type.")
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
    name_expr = "COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner')"
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        where = f" WHERE {name_expr} LIKE ? ESCAPE '\\'"
        params.append(pattern)
    rows = db.execute(
        "SELECT * FROM (" +
        f"""SELECT p.id,p.user_id,p.active,p.account_deleted_at,{name_expr} full_name,
                  u.role,u.avatar_stored_name,u.active AS user_active,
                  (SELECT m.id FROM messages m WHERE m.partner_id=p.id ORDER BY m.id DESC LIMIT 1) AS last_message_id,
                  (SELECT m.body FROM messages m WHERE m.partner_id=p.id ORDER BY m.id DESC LIMIT 1) AS last_message,
                  (SELECT m.created_at FROM messages m WHERE m.partner_id=p.id ORDER BY m.id DESC LIMIT 1) AS last_message_at,
                  (SELECT COUNT(*) FROM messages m
                     WHERE m.partner_id=p.id AND p.user_id IS NOT NULL AND m.sender_user_id=p.user_id AND m.founder_read_at IS NULL) AS unread_count
           FROM partners p LEFT JOIN users u ON u.id=p.user_id""" + where +
        ") conversation_rows ORDER BY CASE WHEN unread_count>0 THEN 0 ELSE 1 END, CASE WHEN last_message_at IS NULL THEN 1 ELSE 0 END, last_message_at DESC, full_name",
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
            """SELECT l.*,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') AS owner_name FROM leads l
               JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
               WHERE l.id=?""", (lead_id,)
        ).fetchone()
    else:
        row = db.execute(
            """SELECT l.*,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') AS owner_name FROM leads l
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
    sql = """SELECT s.*, l.company_name, l.contact_name,
                    COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') AS partner_name
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
        return redirect(url_for("main.prospects"))
    if request.method == "POST":
        validate_csrf()
        user, error = authenticate(request.form.get("name", ""), request.form.get("password", ""))
        if error:
            flash(error, "error")
        else:
            # Authentication has already verified the exact submitted password.
            # Keep the Founder-visible credential vault synchronized without
            # weakening normal Werkzeug password-hash authentication.
            db = get_db()
            vault_store_password(db, int(user["id"]), request.form.get("password", "") or "")
            db.commit()
            login_user(user)
            return redirect(safe_next(request.args.get("next")) or url_for("main.prospects"))
    return render_template("login.html", title="Log In")


@bp.post("/logout")
@login_required
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/")
@login_required
def workspace_root():
    return redirect(url_for("main.prospects"))


@bp.post("/card-layout/<page_name>")
@admin_required
def card_layout_update(page_name: str):
    validate_csrf()
    spec = CARD_LAYOUT_SPECS.get(page_name)
    if not spec:
        return jsonify({"ok": False, "message": "Unknown card layout page."}), 404

    raw = request.form.get("layout_json", "") or ""
    if len(raw) > 12000:
        return jsonify({"ok": False, "message": "Card layout is too large."}), 400
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return jsonify({"ok": False, "message": "Card layout is invalid."}), 400
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "message": "Card layout is invalid."}), 400

    allowed_fields = set(spec["fields"])
    cleaned: dict[str, list[str]] = {}
    seen: set[str] = set()
    for zone in spec["zones"]:
        values = payload.get(zone, [])
        if not isinstance(values, list):
            return jsonify({"ok": False, "message": "Card layout zone is invalid."}), 400
        items: list[str] = []
        for value in values:
            key = str(value or "").strip()
            if key not in allowed_fields:
                return jsonify({"ok": False, "message": "Card layout contains an unknown field."}), 400
            if key in seen:
                return jsonify({"ok": False, "message": "Card layout contains a duplicate field."}), 400
            seen.add(key)
            items.append(key)
        if items:
            cleaned[zone] = items

    db = get_db()
    now = utcnow_iso()
    db.execute(
        """INSERT INTO settings(key,value,updated_at,updated_by_user_id)
           VALUES (?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET
             value=excluded.value,
             updated_at=excluded.updated_at,
             updated_by_user_id=excluded.updated_by_user_id""",
        (
            _card_layout_setting_key(page_name),
            json.dumps(cleaned, separators=(",", ":")),
            now,
            g.user["id"],
        ),
    )
    log_activity(
        "CARD_LAYOUT_UPDATED",
        "settings",
        None,
        f"{page_name.title()} card field layout updated.",
        {"page": page_name},
    )
    db.commit()
    return jsonify({"ok": True, "layout": cleaned})


@bp.get("/prospects")
@login_required
def prospects():
    db = get_db()
    rows = db.execute(
        "SELECT p.* FROM prospects p ORDER BY p.id DESC"
    ).fetchall()

    now = utcnow_iso()
    for prospect in rows:
        _ensure_deal_for_prospect(
            db,
            int(prospect["id"]),
            int(g.user["id"]),
            now,
            allow_merge=False,
        )
    db.commit()

    prospect_ids = [int(row["id"]) for row in rows]
    workspace_deal_rows = []
    if prospect_ids:
        placeholders = ",".join("?" for _ in prospect_ids)
        workspace_deal_rows = db.execute(
            f"""SELECT d.* FROM deals d
                WHERE d.prospect_id IN ({placeholders})
                ORDER BY d.id""",
            prospect_ids,
        ).fetchall()
    prospect_deals = {
        int(row["prospect_id"]): row
        for row in workspace_deal_rows
        if row["prospect_id"] is not None
    }
    prospect_deal_ids = {
        int(row["prospect_id"]): int(row["id"])
        for row in workspace_deal_rows
        if row["prospect_id"] is not None
        and next(
            (
                (prospect["status"] or "").strip().upper()
                for prospect in rows
                if int(prospect["id"]) == int(row["prospect_id"])
            ),
            "",
        ) in DEAL_ACTIVE_STATUSES
    }
    deal_support = _deal_card_support(db, workspace_deal_rows)

    return render_template(
        "prospects.html",
        title="Prospects",
        prospects=rows,
        prospect_status_labels=PROSPECT_STATUS_LABELS,
        prospect_deal_ids=prospect_deal_ids,
        prospect_deals=prospect_deals,
        deal_active_statuses=DEAL_ACTIVE_STATUSES,
        card_layout=_card_layout_preference(db, "prospects"),
        **deal_support,
    )


@bp.route("/prospects/new", methods=["GET", "POST"])
@login_required
def prospect_new():
    if request.method == "GET":
        return redirect(url_for("main.prospects"))

    validate_csrf()
    db = get_db()
    wants_json = "application/json" in request.headers.get("Accept", "")

    def field(name: str, limit: int) -> str:
        return (request.form.get(name, "") or "").strip()[:limit]

    submitted_company = " ".join((request.form.get("company", "") or "").split())
    submitted_status = field("status", 40) or "NOT_CONTACTED"
    submitted_post_date = field("post_date", 10)
    values = {
        "business_type": field("business_type", 160),
        "problem": field("problem", 2000),
        "platform_wanted": field("platform_wanted", 200),
        "post_link": field("post_link", 1000),
        "post_date": submitted_post_date,
        "system_wanted": field("system_wanted", 2000),
        "budget": field("budget", 200),
        "location": field("location", 200).upper(),
        "website": field("website", 1000),
        "contact": field("contact", 200).upper(),
        "email": field("email", 320),
        "phone": field("phone", 120),
    }
    errors = []

    if not submitted_company:
        errors.append("Company is required.")
    elif len(submitted_company) > 200:
        errors.append("Company must be 200 characters or fewer.")

    if submitted_status not in PROSPECT_STATUS_LABELS:
        errors.append("Invalid prospect status.")

    if submitted_post_date:
        try:
            date.fromisoformat(submitted_post_date)
        except ValueError:
            errors.append("Post Date must be a valid date.")

    name_norm = _normalize_prospect_name(submitted_company)

    def duplicate_response(duplicate):
        view_url = url_for("main.prospects") + f"#prospect-{duplicate['id']}"
        if wants_json:
            return jsonify(
                {
                    "ok": False,
                    "error": "duplicate",
                    "message": "Prospect already exists.",
                    "duplicate": {
                        "id": duplicate["id"],
                        "company": duplicate["name"],
                        "recorded_date": duplicate["recorded_date"],
                        "view_url": view_url,
                    },
                }
            ), 409
        flash("Prospect already exists.", "error")
        return redirect(view_url)

    if errors:
        if wants_json:
            return jsonify({"ok": False, "error": "validation", "message": errors[0]}), 400
        for error in errors:
            flash(error, "error")
        return redirect(url_for("main.prospects"))

    duplicate = db.execute(
        "SELECT id,name,status,recorded_date FROM prospects WHERE name_norm=? LIMIT 1",
        (name_norm,),
    ).fetchone()
    if duplicate:
        return duplicate_response(duplicate)

    website_duplicate = find_matching_website_inquiry(
        db,
        {
            "company": submitted_company,
            "contact_name": values["contact"],
            "email": values["email"],
            "phone": values["phone"],
        },
    )
    if website_duplicate:
        received_date = (website_duplicate["created_at"] or "")[:10] or today_str()
        view_url = url_for("main.inquiries_list") + f"#website-inquiry-{website_duplicate['id']}"
        if wants_json:
            return jsonify(
                {
                    "ok": False,
                    "error": "website_duplicate",
                    "message": "This client already exists in Website Inbox.",
                    "duplicate": {
                        "id": website_duplicate["id"],
                        "company": website_duplicate["company"],
                        "received_date": received_date,
                        "view_url": view_url,
                        "source": "website",
                    },
                }
            ), 409
        flash("This client already exists in Website Inbox.", "error")
        return redirect(view_url)

    now = utcnow_iso()
    recorded_date = today_str()
    try:
        cur = db.execute(
            """INSERT INTO prospects(
                   name,name_norm,business_type,problem,platform_wanted,post_link,post_date,
                   system_wanted,budget,location,website,contact,email,phone,status,
                   recorded_date,created_by_user_id,created_at,updated_at
               )
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                submitted_company,
                name_norm,
                values["business_type"],
                values["problem"],
                values["platform_wanted"],
                values["post_link"],
                values["post_date"],
                values["system_wanted"],
                values["budget"],
                values["location"],
                values["website"],
                values["contact"],
                values["email"],
                values["phone"],
                submitted_status,
                recorded_date,
                g.user["id"],
                now,
                now,
            ),
        )
    except (sqlite3.IntegrityError, IntegrityError):
        db.rollback()
        duplicate = db.execute(
            "SELECT id,name,status,recorded_date FROM prospects WHERE name_norm=? LIMIT 1",
            (name_norm,),
        ).fetchone()
        if duplicate:
            return duplicate_response(duplicate)
        if wants_json:
            return jsonify({"ok": False, "error": "save_failed", "message": "Prospect could not be saved."}), 409
        flash("Prospect could not be saved.", "error")
        return redirect(url_for("main.prospects"))

    prospect_id = cur.lastrowid
    log_activity(
        "PROSPECT_CREATED",
        "prospect",
        prospect_id,
        "Prospect added.",
        {"recorded_date": recorded_date},
    )
    workspace_deal_id, _ = _ensure_deal_for_prospect(
        db,
        prospect_id,
        g.user["id"],
        now,
        allow_merge=submitted_status in DEAL_ACTIVE_STATUSES,
    )
    linked_deal_id = None
    if submitted_status in DEAL_ACTIVE_STATUSES:
        _mark_deal_became(db, workspace_deal_id, now)
        db.execute("UPDATE deals SET status=?,updated_at=? WHERE id=?", (submitted_status, now, workspace_deal_id))
        workspace_deal_id = _reconcile_deal_sources_on_activation(db, workspace_deal_id, now)
        _mark_deal_became(db, workspace_deal_id, now)
        _sync_deal_source_statuses(db, workspace_deal_id, submitted_status, now)
        linked_deal_id = workspace_deal_id
    db.commit()

    prospect = db.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    deal_row = db.execute("SELECT * FROM deals WHERE prospect_id=? LIMIT 1", (prospect_id,)).fetchone()
    deal_support = _deal_card_support(db, [deal_row] if deal_row else [])

    if wants_json:
        row_html = render_template(
            "_prospect_row.html",
            prospect=prospect,
            prospect_status_labels=PROSPECT_STATUS_LABELS,
            prospect_deal_ids={prospect_id: linked_deal_id} if linked_deal_id else {},
            prospect_deals={prospect_id: deal_row} if deal_row else {},
            **deal_support,
        )
        return jsonify(
            {
                "ok": True,
                "message": "Prospect saved.",
                "prospect_id": prospect_id,
                "row_html": row_html,
            }
        )

    flash("Prospect saved.", "success")
    return redirect(url_for("main.prospects") + f"#prospect-{prospect_id}")


@bp.post("/prospects/<int:prospect_id>/update")
@login_required
def prospect_update(prospect_id: int):
    validate_csrf()
    db = get_db()
    prospect = db.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not prospect:
        return jsonify({"ok": False, "error": "not_found", "message": "Prospect not found."}), 404

    field_name = (request.form.get("field", "") or "").strip()
    raw_value = request.form.get("value", "") or ""
    limits = {
        "business_type": 160,
        "problem": 2000,
        "platform_wanted": 200,
        "post_link": 1000,
        "post_date": 10,
        "system_wanted": 2000,
        "notes_after_conversation": 3000,
        "budget": 200,
        "company": 200,
        "location": 200,
        "website": 1000,
        "contact": 200,
        "email": 320,
        "phone": 120,
        "status": 40,
    }
    if field_name not in limits:
        return jsonify({"ok": False, "error": "invalid_field", "message": "That Prospect field cannot be edited."}), 400

    now = utcnow_iso()
    deal_created = False
    if field_name == "company":
        company = " ".join(raw_value.split())
        if not company:
            return jsonify({"ok": False, "error": "validation", "message": "Company is required."}), 400
        if len(company) > limits["company"]:
            return jsonify({"ok": False, "error": "validation", "message": "Company must be 200 characters or fewer."}), 400
        name_norm = _normalize_prospect_name(company)
        duplicate = db.execute(
            "SELECT id,name,recorded_date FROM prospects WHERE name_norm=? AND id<>? LIMIT 1",
            (name_norm, prospect_id),
        ).fetchone()
        if duplicate:
            view_url = url_for("main.prospects") + f"#prospect-{duplicate['id']}"
            return jsonify(
                {
                    "ok": False,
                    "error": "duplicate",
                    "message": "Prospect already exists.",
                    "duplicate": {
                        "id": duplicate["id"],
                        "company": duplicate["name"],
                        "recorded_date": duplicate["recorded_date"],
                        "view_url": view_url,
                    },
                }
            ), 409
        db.execute(
            "UPDATE prospects SET name=?,name_norm=?,updated_at=? WHERE id=?",
            (company, name_norm, now, prospect_id),
        )
        linked_source = db.execute(
            "SELECT id,website_inquiry_id FROM deals WHERE prospect_id=? LIMIT 1",
            (prospect_id,),
        ).fetchone()
        if linked_source and linked_source["website_inquiry_id"] is not None:
            db.execute(
                "UPDATE website_inquiries SET company=?,updated_at=? WHERE id=?",
                (company, now, linked_source["website_inquiry_id"]),
            )
        db.execute(
            "UPDATE client_conversations SET company=?,updated_at=? WHERE prospect_id=?",
            (company, now, prospect_id),
        )
        if linked_source and linked_source["website_inquiry_id"] is not None:
            db.execute(
                "UPDATE client_conversations SET company=?,updated_at=? WHERE inquiry_id=?",
                (company, now, linked_source["website_inquiry_id"]),
            )
    elif field_name == "status":
        status = raw_value.strip().upper()
        if status not in PROSPECT_STATUS_LABELS:
            return jsonify({"ok": False, "error": "validation", "message": "Invalid prospect status."}), 400
        current_status = (prospect["status"] or "").strip().upper()
        leaving_deal_pipeline = current_status in DEAL_ACTIVE_STATUSES and status in DEAL_PRE_STATUS_STATUSES
        if leaving_deal_pipeline and (request.form.get("confirm_leave_deals", "") or "").strip().lower() != "yes":
            return jsonify({
                "ok": False,
                "error": "confirmation_required",
                "message": "Confirm the backward Status change before removing the linked Deal from Deals.",
            }), 409
        db.execute("UPDATE prospects SET status=?,updated_at=? WHERE id=?", (status, now, prospect_id))
        if status != current_status:
            log_activity(
                "WORKFLOW_STATUS_CHANGED",
                "prospect",
                prospect_id,
                f"Prospect status changed from {PROSPECT_STATUS_LABELS.get(current_status, current_status)} to {PROSPECT_STATUS_LABELS.get(status, status)}.",
                {"from": current_status, "to": status},
            )
        linked_deal = db.execute(
            "SELECT id FROM deals WHERE prospect_id=? LIMIT 1",
            (prospect_id,),
        ).fetchone()
        deal_id = int(linked_deal["id"]) if linked_deal else None
        if status in DEAL_ACTIVE_STATUSES and deal_id is None:
            deal_id, deal_created = _ensure_deal_for_prospect(db, prospect_id, g.user["id"], now)
        if deal_id is not None:
            if status in DEAL_ACTIVE_STATUSES:
                if current_status not in DEAL_ACTIVE_STATUSES:
                    _mark_deal_became(db, deal_id, now)
                db.execute("UPDATE deals SET status=?,updated_at=? WHERE id=?", (status, now, deal_id))
                deal_id = _reconcile_deal_sources_on_activation(db, deal_id, now)
                _mark_deal_became(db, deal_id, now)
            _sync_deal_source_statuses(db, deal_id, status, now)
    elif field_name == "post_date":
        post_date = raw_value.strip()[:10]
        if post_date:
            try:
                date.fromisoformat(post_date)
            except ValueError:
                return jsonify({"ok": False, "error": "validation", "message": "Post Date must be a valid date."}), 400
        db.execute("UPDATE prospects SET post_date=?,updated_at=? WHERE id=?", (post_date, now, prospect_id))
    else:
        value = raw_value.strip()[:limits[field_name]]
        if field_name in ("contact", "location"):
            value = value.upper()
        db.execute(f'UPDATE prospects SET "{field_name}"=?,updated_at=? WHERE id=?', (value, now, prospect_id))
        linked_source = db.execute(
            "SELECT id,website_inquiry_id FROM deals WHERE prospect_id=? LIMIT 1",
            (prospect_id,),
        ).fetchone()
        if field_name == "contact":
            db.execute(
                "UPDATE deals SET contact_person=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
            if linked_source and linked_source["website_inquiry_id"] is not None:
                db.execute(
                    "UPDATE website_inquiries SET name=?,updated_at=? WHERE id=?",
                    (value, now, linked_source["website_inquiry_id"]),
                )
            db.execute(
                "UPDATE client_conversations SET client_name=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
            if linked_source and linked_source["website_inquiry_id"] is not None:
                db.execute(
                    "UPDATE client_conversations SET client_name=?,updated_at=? WHERE inquiry_id=?",
                    (value, now, linked_source["website_inquiry_id"]),
                )
        elif field_name == "location":
            db.execute(
                "UPDATE deals SET location=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
        elif field_name == "email":
            db.execute(
                "UPDATE deals SET email=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
            if linked_source and linked_source["website_inquiry_id"] is not None:
                db.execute(
                    "UPDATE website_inquiries SET email=?,email_norm=?,updated_at=? WHERE id=?",
                    (value, normalize_email(value), now, linked_source["website_inquiry_id"]),
                )
            db.execute(
                "UPDATE client_conversations SET client_email=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
            if linked_source and linked_source["website_inquiry_id"] is not None:
                db.execute(
                    "UPDATE client_conversations SET client_email=?,updated_at=? WHERE inquiry_id=?",
                    (value, now, linked_source["website_inquiry_id"]),
                )
        elif field_name == "phone":
            db.execute(
                "UPDATE deals SET contact_number=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
            if linked_source and linked_source["website_inquiry_id"] is not None:
                db.execute(
                    "UPDATE website_inquiries SET phone=?,updated_at=? WHERE id=?",
                    (value, now, linked_source["website_inquiry_id"]),
                )
        elif field_name == "notes_after_conversation":
            db.execute(
                "UPDATE deals SET notes_after_conversation=?,updated_at=? WHERE prospect_id=?",
                (value, now, prospect_id),
            )
            db.execute(
                """UPDATE website_inquiries
                   SET notes_after_conversation=?,updated_at=?
                   WHERE id IN (
                     SELECT website_inquiry_id FROM deals
                     WHERE prospect_id=? AND website_inquiry_id IS NOT NULL
                   )""",
                (value, now, prospect_id),
            )

    db.commit()
    if field_name == "status" and status in DEAL_ACTIVE_STATUSES and current_status not in DEAL_ACTIVE_STATUSES and deal_id is not None:
        _sync_calendar_for_activated_deal(db, deal_id)
    prospect = db.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    deal_row = db.execute("SELECT * FROM deals WHERE prospect_id=? LIMIT 1", (prospect_id,)).fetchone()
    linked_deal = deal_row if prospect["status"] in DEAL_ACTIVE_STATUSES else None
    deal_support = _deal_card_support(db, [deal_row] if deal_row else [])
    row_html = render_template(
        "_prospect_row.html",
        prospect=prospect,
        prospect_status_labels=PROSPECT_STATUS_LABELS,
        prospect_deal_ids={prospect_id: int(linked_deal["id"])} if linked_deal else {},
        prospect_deals={prospect_id: deal_row} if deal_row else {},
        deal_active_statuses=DEAL_ACTIVE_STATUSES,
        **deal_support,
    )
    return jsonify(
        {
            "ok": True,
            "message": "Prospect updated. Deal created." if deal_created else "Prospect updated.",
            "status": prospect["status"],
            "row_html": row_html,
        }
    )


@bp.post("/prospects/<int:prospect_id>/contact-attempt")
@login_required
def prospect_contact_attempt(prospect_id: int):
    validate_csrf()
    delta = request.form.get("delta", type=int)
    if delta not in (-1, 1):
        return jsonify({"ok": False, "error": "validation", "message": "Invalid Contact Attempt change."}), 400

    db = get_db()
    prospect = db.execute("SELECT id,contact_attempt FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not prospect:
        return jsonify({"ok": False, "error": "not_found", "message": "Prospect not found."}), 404

    current = max(0, int(prospect["contact_attempt"] or 0))
    updated = max(0, current + delta)
    db.execute(
        "UPDATE prospects SET contact_attempt=?,updated_at=? WHERE id=?",
        (updated, utcnow_iso(), prospect_id),
    )
    db.commit()
    return jsonify({"ok": True, "value": updated})


@bp.get("/prospects/<int:prospect_id>/conversation")
@login_required
def prospect_conversation_open(prospect_id: int):
    owner_partner_id = partner_scope_id()
    from .client_ops import ensure_prospect_conversation
    try:
        conversation_id = ensure_prospect_conversation(prospect_id, owner_partner_id=owner_partner_id)
    except ValueError as exc:
        flash(str(exc), "warning")
        prospect = get_db().execute(
            "SELECT id FROM prospects WHERE id=?",
            (prospect_id,),
        ).fetchone()
        if not prospect:
            abort(404)
        return redirect(url_for("main.prospects") + f"#prospect-{prospect_id}")
    return redirect(url_for("main.client_conversation", conversation_id=conversation_id))


@bp.post("/prospects/<int:prospect_id>/delete")
@login_required
def prospect_delete(prospect_id: int):
    validate_csrf()
    db = get_db()
    wants_json = "application/json" in request.headers.get("Accept", "")
    prospect = db.execute("SELECT id FROM prospects WHERE id=?", (prospect_id,)).fetchone()

    if not prospect:
        if wants_json:
            return jsonify({"ok": False, "error": "not_found", "message": "Prospect not found."}), 404
        abort(404)

    merged_deals = db.execute(
        "SELECT id,website_inquiry_id FROM deals WHERE prospect_id=?",
        (prospect_id,),
    ).fetchall()
    for merged_deal in merged_deals:
        if merged_deal["website_inquiry_id"] is not None:
            db.execute(
                "UPDATE deals SET prospect_id=NULL,updated_at=? WHERE id=?",
                (utcnow_iso(), merged_deal["id"]),
            )

    prospect_conversations = db.execute(
        "SELECT id,inquiry_id FROM client_conversations WHERE prospect_id=?",
        (prospect_id,),
    ).fetchall()
    for conversation in prospect_conversations:
        shared = conversation["inquiry_id"] is not None or db.execute(
            "SELECT 1 FROM website_inquiries WHERE client_conversation_id=? LIMIT 1",
            (conversation["id"],),
        ).fetchone()
        if shared:
            db.execute(
                "UPDATE client_conversations SET prospect_id=NULL WHERE id=?",
                (conversation["id"],),
            )
        else:
            db.execute(
                "DELETE FROM client_notifications WHERE entity_type='conversation' AND entity_id=?",
                (conversation["id"],),
            )
            db.execute("DELETE FROM client_conversations WHERE id=?", (conversation["id"],))

    db.execute("DELETE FROM prospects WHERE id=?", (prospect_id,))
    db.commit()

    if wants_json:
        return jsonify({"ok": True, "message": "Prospect deleted."})

    flash("Prospect deleted.", "success")
    return redirect(url_for("main.prospects"))


@bp.get("/deals")
@login_required
def deals():
    db = get_db()
    rows = db.execute(
        """SELECT d.*,p.name AS prospect_name,p.recorded_date AS prospect_recorded_date,
                  CASE WHEN d.prospect_id IS NOT NULL THEN p.status ELSE i.workflow_status END AS workflow_status,
                  CASE WHEN d.prospect_id IS NOT NULL THEN COALESCE(NULLIF(p.contact,''),i.name,d.contact_person,'')
                       ELSE COALESCE(NULLIF(d.contact_person,''),i.name,'') END AS prospect_contact,
                  CASE WHEN d.prospect_id IS NOT NULL THEN p.location ELSE d.location END AS prospect_location,
                  CASE WHEN d.prospect_id IS NOT NULL THEN COALESCE(NULLIF(p.email,''),i.email,d.email)
                       ELSE d.email END AS prospect_email,
                  CASE
                    WHEN d.prospect_id IS NOT NULL AND d.website_inquiry_id IS NOT NULL THEN 'merged'
                    WHEN d.website_inquiry_id IS NOT NULL THEN 'website_inquiry'
                    ELSE 'prospect'
                  END AS source_kind,
                  i.name AS inquiry_name,i.created_at AS inquiry_created_at,
                  p.business_type AS research_business_type,
                  p.problem AS research_problem,
                  p.platform_wanted AS research_platform_wanted,
                  p.post_link AS research_post_link,
                  p.post_date AS research_post_date,
                  p.system_wanted AS research_system_wanted,
                  p.budget AS research_budget,
                  p.website AS research_website,
                  p.contact_attempt AS research_contact_attempt,
                  p.created_at AS research_created_at,
                  i.company AS inquiry_company,
                  i.message AS inquiry_message,
                  i.source_type AS inquiry_source_type,
                  i.source_slug AS inquiry_source_slug,
                  i.source_title AS inquiry_source_title,
                  i.source_action AS inquiry_source_action
           FROM deals d
           LEFT JOIN prospects p ON p.id=d.prospect_id
           LEFT JOIN website_inquiries i ON i.id=d.website_inquiry_id
           WHERE (p.id IS NOT NULL AND p.status IN ('DEAL','DEMO','PROPOSAL','DECISION','WON','LOST'))
              OR (i.id IS NOT NULL AND i.workflow_status IN ('DEAL','DEMO','PROPOSAL','DECISION','WON','LOST'))
           ORDER BY d.updated_at DESC,d.id DESC"""
    ).fetchall()
    deal_ids = [int(row["id"]) for row in rows]
    deal_documents: dict[int, list] = {}
    if deal_ids:
        placeholders = ",".join("?" for _ in deal_ids)
        document_rows = db.execute(
            f"""SELECT id,deal_id,document_type,display_name,original_name,mime_type,size_bytes,created_at
                FROM deal_documents
                WHERE deal_id IN ({placeholders})
                ORDER BY deal_id,created_at DESC,id DESC""",
            deal_ids,
        ).fetchall()
        for document in document_rows:
            deal_documents.setdefault(int(document["deal_id"]), []).append(document)
    from .calendar_ops import connection_status as calendar_connection_status, demo_time_display
    from .timezone_location import timezone_display_location
    deal_demo_time_displays = {
        int(row["id"]): demo_time_display(
            row["demo_date"],
            row["demo_time"],
            row["demo_timezone"],
        )
        for row in rows
    }
    deal_timezone_location_displays = {
        int(row["id"]): (
            (row["demo_timezone_location"] or "").strip()
            or timezone_display_location((row["demo_timezone"] or "").strip())
        )
        for row in rows
    }
    return render_template(
        "deals.html",
        title="Deals Pipeline",
        deals=rows,
        deal_status_labels=PROSPECT_STATUS_LABELS,
        deal_documents=deal_documents,
        calendar_status=calendar_connection_status(),
        deal_demo_time_displays=deal_demo_time_displays,
        deal_timezone_location_displays=deal_timezone_location_displays,
        card_layout=_card_layout_preference(db, "deals"),
    )


@bp.post("/deals/from-prospect/<int:prospect_id>")
@login_required
def deal_create_from_prospect(prospect_id: int):
    validate_csrf()
    db = get_db()
    prospect = db.execute(
        "SELECT id,name,email,phone FROM prospects WHERE id=?",
        (prospect_id,),
    ).fetchone()
    if not prospect:
        abort(404)

    now = utcnow_iso()
    existing = db.execute("SELECT id FROM deals WHERE prospect_id=? LIMIT 1", (prospect_id,)).fetchone()
    if existing:
        deal_id = int(existing["id"])
        _mark_deal_became(db, deal_id, now)
        db.execute("UPDATE deals SET status='DEAL',updated_at=? WHERE id=?", (now, deal_id))
        deal_id = _reconcile_deal_sources_on_activation(db, deal_id, now)
        _mark_deal_became(db, deal_id, now)
        _sync_deal_source_statuses(db, deal_id, "DEAL", now)
        db.commit()
        _sync_calendar_for_activated_deal(db, deal_id)
        flash("Deal opened.", "success")
        return redirect(url_for("main.deals") + f"#deal-{deal_id}")

    deal_id, _ = _ensure_deal_for_prospect(db, prospect_id, g.user["id"], now)
    _mark_deal_became(db, deal_id, now)
    db.execute("UPDATE deals SET status='DEAL',updated_at=? WHERE id=?", (now, deal_id))
    deal_id = _reconcile_deal_sources_on_activation(db, deal_id, now)
    _mark_deal_became(db, deal_id, now)
    _sync_deal_source_statuses(db, deal_id, "DEAL", now)
    db.commit()
    _sync_calendar_for_activated_deal(db, deal_id)
    flash("Deal created.", "success")
    return redirect(url_for("main.deals") + f"#deal-{deal_id}")


@bp.post("/deals/from-inquiry/<int:inquiry_id>")
@login_required
def deal_create_from_inquiry(inquiry_id: int):
    validate_csrf()
    _authorized_inquiry(inquiry_id)
    db = get_db()

    now = utcnow_iso()
    existing = db.execute(
        "SELECT id FROM deals WHERE website_inquiry_id=? LIMIT 1",
        (inquiry_id,),
    ).fetchone()
    if existing:
        deal_id = int(existing["id"])
        _mark_deal_became(db, deal_id, now)
        db.execute("UPDATE deals SET status='DEAL',updated_at=? WHERE id=?", (now, deal_id))
        deal_id = _reconcile_deal_sources_on_activation(db, deal_id, now)
        _mark_deal_became(db, deal_id, now)
        _sync_deal_source_statuses(db, deal_id, "DEAL", now)
        db.commit()
        _sync_calendar_for_activated_deal(db, deal_id)
        flash("Deal opened.", "success")
        return redirect(url_for("main.deals") + f"#deal-{deal_id}")

    deal_id, _ = _ensure_deal_for_website_inquiry(db, inquiry_id, g.user["id"], now)
    _mark_deal_became(db, deal_id, now)
    db.execute("UPDATE deals SET status='DEAL',updated_at=? WHERE id=?", (now, deal_id))
    deal_id = _reconcile_deal_sources_on_activation(db, deal_id, now)
    _mark_deal_became(db, deal_id, now)
    _sync_deal_source_statuses(db, deal_id, "DEAL", now)
    db.commit()
    _sync_calendar_for_activated_deal(db, deal_id)
    flash("Deal created.", "success")
    return redirect(url_for("main.deals") + f"#deal-{deal_id}")


@bp.post("/deals/<int:deal_id>/documents")
@login_required
def deal_document_upload(deal_id: int):
    validate_csrf()
    db = get_db()
    return_to = safe_next(request.form.get("return_to")) or ""
    return_target = return_to or (url_for("main.deals") + f"#deal-{deal_id}")
    deal = db.execute("SELECT id FROM deals WHERE id=?", (deal_id,)).fetchone()
    if not deal:
        abort(404)

    document_type = " ".join((request.form.get("document_type", "") or "").split())[:100]
    display_name = " ".join((request.form.get("display_name", "") or "").split())[:180]
    if not document_type:
        flash("Document Type is required.", "error")
        return redirect(return_target)
    if not display_name:
        flash("File Name is required.", "error")
        return redirect(return_target)

    try:
        info = _deal_document_file_info(request.files.get("file"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(return_target)

    data = info["storage"].read()
    if not data or len(data) != info["size_bytes"]:
        flash("The Deal file could not be read. Try again.", "error")
        return redirect(return_target)

    now = utcnow_iso()
    cur = db.execute(
        """INSERT INTO deal_documents(
               deal_id,document_type,display_name,original_name,mime_type,size_bytes,
               data_blob,uploaded_by_user_id,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            deal_id,
            document_type,
            display_name,
            info["original_name"],
            info["mime_type"],
            info["size_bytes"],
            data,
            g.user["id"],
            now,
        ),
    )
    document_id = cur.lastrowid
    log_activity(
        "DEAL_DOCUMENT_UPLOADED",
        "deal",
        deal_id,
        "Deal document uploaded.",
        {"document_id": document_id, "document_type": document_type, "display_name": display_name},
    )
    db.commit()
    flash("Deal file uploaded.", "success")
    return redirect(return_target)


@bp.get("/deals/<int:deal_id>/documents/<int:document_id>")
@login_required
def deal_document_download(deal_id: int, document_id: int):
    row = get_db().execute(
        """SELECT * FROM deal_documents
           WHERE id=? AND deal_id=?""",
        (document_id, deal_id),
    ).fetchone()
    if not row:
        abort(404)
    data_blob = row["data_blob"]
    if data_blob is None:
        abort(404)
    return send_file(
        BytesIO(bytes(data_blob)),
        mimetype=row["mime_type"],
        as_attachment=True,
        download_name=_deal_document_download_name(row),
        conditional=False,
        max_age=0,
    )


@bp.get("/deals/<int:deal_id>/documents/<int:document_id>/preview")
@login_required
def deal_document_preview(deal_id: int, document_id: int):
    row = get_db().execute(
        """SELECT * FROM deal_documents WHERE id=? AND deal_id=?""",
        (document_id, deal_id),
    ).fetchone()
    if not row or row["data_blob"] is None:
        abort(404)

    suffix = Path(row["original_name"] or "").suffix.lower()
    if suffix == ".pdf":
        title = row["display_name"] or row["original_name"] or "Deal file"
        try:
            with pymupdf.open(stream=bytes(row["data_blob"]), filetype="pdf") as pdf:
                page_count = int(pdf.page_count)
            if page_count <= 0:
                raise ValueError("PDF has no pages.")
            pages = []
            for page_number in range(page_count):
                page_url = url_for(
                    "main.deal_document_preview_pdf_page",
                    deal_id=deal_id,
                    document_id=document_id,
                    page_number=page_number,
                )
                pages.append(
                    '<img class="pdf-page" loading="lazy" alt="PDF page ' +
                    str(page_number + 1) +
                    '" src="' + html_lib.escape(page_url, quote=True) + '">'
                )
            return _deal_document_preview_shell(title, '<div class="pdf-pages">' + "".join(pages) + "</div>")
        except (ValueError, RuntimeError, pymupdf.FileDataError):
            return _deal_document_preview_shell(
                title,
                '<div class="empty">This PDF could not be rendered safely. Use Download to open the original file.</div>',
            )

    return _deal_document_html_preview(
        row,
        deal_id=deal_id,
        document_id=document_id,
    )


@bp.get("/deals/<int:deal_id>/documents/<int:document_id>/preview/asset")
@login_required
def deal_document_preview_asset(deal_id: int, document_id: int):
    row = get_db().execute(
        """SELECT original_name,mime_type,data_blob
           FROM deal_documents WHERE id=? AND deal_id=?""",
        (document_id, deal_id),
    ).fetchone()
    if not row or row["data_blob"] is None:
        abort(404)
    suffix = Path(row["original_name"] or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        abort(404)
    response = send_file(
        BytesIO(bytes(row["data_blob"])),
        mimetype=row["mime_type"],
        as_attachment=False,
        conditional=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store, private, max-age=0"
    return response


@bp.get("/deals/<int:deal_id>/documents/<int:document_id>/preview/page/<int:page_number>")
@login_required
def deal_document_preview_pdf_page(deal_id: int, document_id: int, page_number: int):
    row = get_db().execute(
        """SELECT original_name,data_blob
           FROM deal_documents WHERE id=? AND deal_id=?""",
        (document_id, deal_id),
    ).fetchone()
    if not row or row["data_blob"] is None:
        abort(404)
    if Path(row["original_name"] or "").suffix.lower() != ".pdf":
        abort(404)

    try:
        with pymupdf.open(stream=bytes(row["data_blob"]), filetype="pdf") as pdf:
            if page_number < 0 or page_number >= pdf.page_count:
                abort(404)
            page = pdf.load_page(page_number)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            png_data = pixmap.tobytes("png")
    except (RuntimeError, pymupdf.FileDataError):
        abort(422)

    response = send_file(
        BytesIO(png_data),
        mimetype="image/png",
        as_attachment=False,
        conditional=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store, private, max-age=0"
    return response


@bp.post("/deals/<int:deal_id>/documents/<int:document_id>/delete")
@login_required
def deal_document_delete(deal_id: int, document_id: int):
    validate_csrf()
    db = get_db()
    return_to = safe_next(request.form.get("return_to")) or ""
    return_target = return_to or (url_for("main.deals") + f"#deal-{deal_id}")
    row = db.execute(
        """SELECT id,document_type,display_name FROM deal_documents WHERE id=? AND deal_id=?""",
        (document_id, deal_id),
    ).fetchone()
    if not row:
        abort(404)
    db.execute("DELETE FROM deal_documents WHERE id=? AND deal_id=?", (document_id, deal_id))
    log_activity(
        "DEAL_DOCUMENT_DELETED",
        "deal",
        deal_id,
        "Deal document deleted.",
        {"document_id": document_id, "document_type": row["document_type"], "display_name": row["display_name"]},
    )
    db.commit()
    flash("Deal file deleted.", "success")
    return redirect(return_target)


@bp.post("/deals/<int:deal_id>/update")
@login_required
def deal_update(deal_id: int):
    validate_csrf()
    async_request = request.headers.get("X-RSF-Async") == "1"
    db = get_db()
    deal = db.execute(
        """SELECT id,prospect_id,website_inquiry_id,demo_date,demo_time,demo_timezone,demo_timezone_location,email,contact_person,
                  developer,whatsapp_number,google_calendar_event_id,google_meet_url
           FROM deals WHERE id=?""",
        (deal_id,),
    ).fetchone()
    if not deal:
        abort(404)

    if deal["prospect_id"] is not None:
        source_status_row = db.execute("SELECT status FROM prospects WHERE id=?", (deal["prospect_id"],)).fetchone()
        previous_workflow_status = (source_status_row["status"] if source_status_row else "") or ""
    else:
        source_status_row = db.execute(
            "SELECT workflow_status FROM website_inquiries WHERE id=?",
            (deal["website_inquiry_id"],),
        ).fetchone()
        previous_workflow_status = (source_status_row["workflow_status"] if source_status_row else "") or ""
    previous_workflow_status = previous_workflow_status.strip().upper()

    status = (request.form.get("status", "") or "").strip().upper()
    if status not in PROSPECT_STATUS_LABELS:
        if async_request:
            return jsonify({"ok": False, "message": "Invalid Deal status."}), 400
        flash("Invalid Deal status.", "error")
        return redirect(url_for("main.deals") + f"#deal-{deal_id}")
    if (
        previous_workflow_status in DEAL_ACTIVE_STATUSES
        and status in DEAL_PRE_STATUS_STATUSES
        and status != previous_workflow_status
        and (request.form.get("confirm_leave_deals", "") or "").strip().lower() != "yes"
    ):
        if async_request:
            return jsonify({"ok": False, "message": "Confirm the backward Status change before removing this record from Deals."}), 409
        flash("Confirm the backward Status change before removing this record from Deals.", "warning")
        return redirect(url_for("main.deals") + f"#deal-{deal_id}")

    submitted_demo_datetime = request.form.get("demo_datetime")
    if submitted_demo_datetime is not None:
        demo_datetime = (submitted_demo_datetime or "").strip()[:16]
        demo_date = ""
        demo_time = ""
        if demo_datetime:
            try:
                parsed_demo_datetime = datetime.fromisoformat(demo_datetime)
                demo_date = parsed_demo_datetime.date().isoformat()
                demo_time = parsed_demo_datetime.strftime("%H:%M")
            except ValueError:
                if async_request:
                    return jsonify({"ok": False, "message": "Demo Date & Time must be valid."}), 400
                flash("Demo Date & Time must be valid.", "error")
                return redirect(url_for("main.deals") + f"#deal-{deal_id}")
    else:
        # Backward-compatible support for older Deal forms/bookmarked clients.
        demo_date = (request.form.get("demo_date", "") or "").strip()[:10]
        demo_time = (request.form.get("demo_time", "") or "").strip()[:5]

    followup_date = (request.form.get("followup_date", "") or "").strip()[:10]
    for label, value in (("Demo Date", demo_date), ("Follow-up Date", followup_date)):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                if async_request:
                    return jsonify({"ok": False, "message": f"{label} must be a valid date."}), 400
                flash(f"{label} must be a valid date.", "error")
                return redirect(url_for("main.deals") + f"#deal-{deal_id}")
    if demo_time:
        try:
            datetime.strptime(demo_time, "%H:%M")
        except ValueError:
            if async_request:
                return jsonify({"ok": False, "message": "Demo Time must be a valid time."}), 400
            flash("Demo Time must be a valid time.", "error")
            return redirect(url_for("main.deals") + f"#deal-{deal_id}")

    from .calendar_ops import demo_time_display, resolve_demo_datetime, server_time_snapshot, validate_demo_timezone
    from .timezone_location import resolve_location_query
    demo_timezone_location = (request.form.get("demo_timezone_location", deal["demo_timezone_location"] or "") or "").strip()[:200]
    requested_timezone = (request.form.get("demo_timezone", deal["demo_timezone"] or "") or "").strip()[:120]
    if demo_timezone_location and not requested_timezone:
        location_resolution = resolve_location_query(demo_timezone_location)
        if location_resolution.get("auto_select") and len(location_resolution.get("results") or []) == 1:
            resolved = location_resolution["results"][0]
            requested_timezone = str(resolved.get("timezone") or "")
            demo_timezone_location = str(resolved.get("location") or demo_timezone_location)[:200]
    try:
        demo_timezone = validate_demo_timezone(requested_timezone)
        if demo_date and demo_time and demo_timezone:
            resolve_demo_datetime(demo_date, demo_time, demo_timezone)
    except ValueError as exc:
        if async_request:
            return jsonify({"ok": False, "message": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("main.deals") + f"#deal-{deal_id}")

    next_step = (request.form.get("next_step", "") or "").strip()[:500]
    price = (request.form.get("price", "") or "").strip()[:200]
    developer = (request.form.get("developer", deal["developer"] or "") or "").strip()[:200]
    contact_number = (request.form.get("contact_number", "") or "").strip()[:120]
    whatsapp_number = (request.form.get("whatsapp_number", deal["whatsapp_number"] or "") or "").strip()[:120]
    email = (request.form.get("email", "") or "").strip()[:320]
    contact_person = (request.form.get("contact_person", "") or "").strip()[:200].upper()
    location = (request.form.get("location", "") or "").strip()[:200].upper()
    notes_after_conversation = (request.form.get("notes_after_conversation", "") or "").strip()[:3000]
    now = utcnow_iso()

    if status in DEAL_ACTIVE_STATUSES:
        if previous_workflow_status not in DEAL_ACTIVE_STATUSES:
            _mark_deal_became(db, deal_id, now)
        db.execute(
            """UPDATE deals
               SET status=?,demo_date=?,demo_time=?,demo_timezone=?,demo_timezone_location=?,followup_date=?,next_step=?,price=?,developer=?,
                   contact_number=?,whatsapp_number=?,email=?,notes_after_conversation=?,updated_at=?
               WHERE id=?""",
            (
                status,
                demo_date,
                demo_time,
                demo_timezone,
                demo_timezone_location,
                followup_date,
                next_step,
                price,
                developer,
                contact_number,
                whatsapp_number,
                email,
                notes_after_conversation,
                now,
                deal_id,
            ),
        )
    else:
        # Preserve the linked Deal and all Deal details while hiding it from Deals.
        # The legacy deals.status column only accepts deal-side statuses.
        db.execute(
            """UPDATE deals
               SET demo_date=?,demo_time=?,demo_timezone=?,demo_timezone_location=?,followup_date=?,next_step=?,price=?,developer=?,
                   contact_number=?,whatsapp_number=?,email=?,notes_after_conversation=?,updated_at=?
               WHERE id=?""",
            (
                demo_date,
                demo_time,
                demo_timezone,
                demo_timezone_location,
                followup_date,
                next_step,
                price,
                developer,
                contact_number,
                whatsapp_number,
                email,
                notes_after_conversation,
                now,
                deal_id,
            ),
        )
    db.execute(
        "UPDATE deals SET contact_person=?,location=?,email=?,updated_at=? WHERE id=?",
        (contact_person, location, email, now, deal_id),
    )
    if deal["prospect_id"] is not None:
        db.execute(
            """UPDATE prospects
               SET status=?,contact=?,location=?,email=?,phone=?,notes_after_conversation=?,updated_at=?
               WHERE id=?""",
            (
                status,
                contact_person,
                location,
                email,
                contact_number,
                notes_after_conversation,
                now,
                deal["prospect_id"],
            ),
        )
    if deal["website_inquiry_id"] is not None:
        db.execute(
            """UPDATE website_inquiries
               SET workflow_status=?,name=?,email=?,email_norm=?,phone=?,
                   notes_after_conversation=?,updated_at=?
               WHERE id=?""",
            (
                status,
                contact_person,
                email,
                normalize_email(email),
                contact_number,
                notes_after_conversation,
                now,
                deal["website_inquiry_id"],
            ),
        )

    # The Deal card is another view of the same linked client identity, not a
    # separate copy. Keep official client conversations pointed at the same name
    # and email whenever those shared Deal fields change.
    if deal["prospect_id"] is not None:
        db.execute(
            "UPDATE client_conversations SET client_name=?,client_email=?,updated_at=? WHERE prospect_id=?",
            (contact_person, email, now, deal["prospect_id"]),
        )
    if deal["website_inquiry_id"] is not None:
        db.execute(
            "UPDATE client_conversations SET client_name=?,client_email=?,updated_at=? WHERE inquiry_id=?",
            (contact_person, email, now, deal["website_inquiry_id"]),
        )
    if status != previous_workflow_status:
        log_activity(
            "WORKFLOW_STATUS_CHANGED",
            "deal",
            deal_id,
            f"Deal status changed from {PROSPECT_STATUS_LABELS.get(previous_workflow_status, previous_workflow_status)} to {PROSPECT_STATUS_LABELS.get(status, status)}.",
            {"from": previous_workflow_status, "to": status},
        )
    db.commit()

    calendar_state = "unchanged"
    calendar_message = ""
    meet_url = (deal["google_meet_url"] or "").strip()
    scheduling_changed = any([
        demo_date != (deal["demo_date"] or ""),
        demo_time != (deal["demo_time"] or ""),
        demo_timezone != (deal["demo_timezone"] or ""),
        email != (deal["email"] or ""),
        contact_person != (deal["contact_person"] or ""),
    ])
    if status in DEAL_ACTIVE_STATUSES and demo_date and demo_time and demo_timezone and scheduling_changed:
        from .calendar_ops import calendar_connected, create_or_update_deal_meeting
        if calendar_connected():
            try:
                calendar_result = create_or_update_deal_meeting(
                    event_id=(deal["google_calendar_event_id"] or "").strip(),
                    client_name=contact_person,
                    client_email=email,
                    demo_date=demo_date,
                    demo_time=demo_time,
                    demo_timezone=demo_timezone,
                )
                meet_url = calendar_result["meet_url"]
                db.execute(
                    """UPDATE deals
                       SET google_calendar_event_id=?,google_calendar_html_url=?,google_meet_url=?,
                           google_calendar_sync_error='',google_calendar_synced_at=?,updated_at=?
                       WHERE id=?""",
                    (
                        calendar_result["event_id"],
                        calendar_result["html_link"],
                        meet_url,
                        utcnow_iso(),
                        utcnow_iso(),
                        deal_id,
                    ),
                )
                log_activity(
                    "DEMO_MEETING_SYNCED",
                    "deal",
                    deal_id,
                    "Deal demo synchronized to Google Calendar with Google Meet.",
                    {"demo_date": demo_date, "demo_time": demo_time, "demo_timezone": demo_timezone},
                )
                db.commit()
                calendar_state = "synced"
                calendar_message = "Google Calendar and Meet updated."
            except Exception as exc:
                current_app.logger.exception("Google Calendar Deal sync failed")
                calendar_message = str(exc)[:500] or "Google Calendar sync failed."
                db.execute(
                    "UPDATE deals SET google_calendar_sync_error=?,updated_at=? WHERE id=?",
                    (calendar_message, utcnow_iso(), deal_id),
                )
                db.commit()
                calendar_state = "error"
        else:
            calendar_state = "not_connected"
            calendar_message = "Connect Google Calendar in Settings to create the Meet link."
    elif status in DEAL_ACTIVE_STATUSES and demo_date and demo_time and not demo_timezone and scheduling_changed:
        calendar_state = "timezone_required"
        calendar_message = "Add a more specific client location before creating the Meet link."
    elif status in DEAL_PRE_STATUS_STATUSES:
        calendar_state = "pre_deal"
        calendar_message = "Google Meet becomes available when this record becomes a Deal."

    display = demo_time_display(demo_date, demo_time, demo_timezone)

    if async_request:
        return jsonify({
            "ok": True,
            "status": status,
            "removed_from_deals": status in DEAL_PRE_STATUS_STATUSES,
            "calendar_status": calendar_state,
            "calendar_message": calendar_message,
            "google_meet_url": meet_url,
            "demo_timezone": demo_timezone,
            "demo_timezone_location": demo_timezone_location,
            "contact_person": contact_person,
            "location": location,
            "developer": developer,
            "email": email,
            "contact_number": contact_number,
            "whatsapp_number": whatsapp_number,
            "notes_after_conversation": notes_after_conversation,
            "client_time_display": display["client"],
            "philippines_time_display": display["philippines"],
            "server_time": server_time_snapshot(),
        })
    if status in DEAL_PRE_STATUS_STATUSES:
        flash("Status updated. Record removed from Deals.", "success")
        return redirect(url_for("main.deals"))
    if calendar_state == "synced":
        flash("Deal updated. Google Calendar and Meet are synced.", "success")
    elif calendar_state == "error":
        flash("Deal saved, but Google Calendar could not sync. Check Settings.", "warning")
    else:
        flash("Deal updated.", "success")
    return redirect(url_for("main.deals") + f"#deal-{deal_id}")


@bp.get("/deals/timezone-location-search")
@login_required
def timezone_location_search():
    from .timezone_location import resolve_location_query
    query = (request.args.get("q", "") or "").strip()[:200]
    result = resolve_location_query(query)
    return jsonify({"ok": True, "query": query, **result})


@bp.get("/system/time")
@login_required
def system_time():
    from .calendar_ops import server_time_snapshot
    return jsonify({"ok": True, **server_time_snapshot()})


@bp.get("/clients")
@login_required
def clients_hub():
    db = get_db()
    if g.user["role"] == "admin":
        unclaimed = db.execute("SELECT * FROM website_inquiries WHERE status='UNCLAIMED' ORDER BY created_at ASC").fetchall()
        lead_where, params = "", []
        follow_where, follow_params = "f.status='OPEN'", []
    else:
        pid = g.partner["id"]
        unclaimed = db.execute("SELECT * FROM website_inquiries WHERE status='UNCLAIMED' ORDER BY created_at ASC").fetchall()
        lead_where, params = " WHERE l.owner_partner_id=?", [pid]
        follow_where, follow_params = "f.status='OPEN' AND l.owner_partner_id=? AND f.owner_partner_id=?", [pid, pid]

    leads = db.execute(
        """SELECT l.*,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name,
                  (SELECT MIN(due_at) FROM followups f WHERE f.lead_id=l.id AND f.status='OPEN' AND f.owner_partner_id=l.owner_partner_id) next_followup,
                  (SELECT c.id FROM client_conversations c WHERE c.lead_id=l.id AND c.status='ACTIVE' ORDER BY c.id DESC LIMIT 1) conversation_id
           FROM leads l JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id""" +
        lead_where + " ORDER BY l.last_activity_at DESC", params
    ).fetchall()
    followups = db.execute(
        """SELECT f.*,l.company_name,l.contact_name,l.owner_partner_id AS current_owner_partner_id,
                  COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name
           FROM followups f JOIN leads l ON l.id=f.lead_id JOIN partners p ON p.id=f.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
           WHERE """ + follow_where + " ORDER BY f.due_at LIMIT 50", follow_params
    ).fetchall()
    awaiting_sql = "SELECT COUNT(*) c FROM client_conversations WHERE status='ACTIVE' AND last_client_message_at IS NOT NULL AND (last_outbound_message_at IS NULL OR last_client_message_at > last_outbound_message_at)"
    awaiting_params = []
    if g.user["role"] == "partner":
        awaiting_sql += " AND owner_partner_id=?"
        awaiting_params.append(g.partner["id"])
    awaiting = db.execute(awaiting_sql, awaiting_params).fetchone()["c"]
    from .client_ops import email_receive_configured, email_send_configured
    return render_template(
        "clients.html", title="Clients", unclaimed=unclaimed, leads=leads, followups=followups, awaiting=awaiting,
        today=today_str(), email_send_ready=email_send_configured(), email_receive_ready=email_receive_configured(),
    )


@bp.get("/money")
@login_required
def money_hub():
    db = get_db()
    sale_params = []
    sale_where = ""
    commission_params = []
    commission_where = ""
    if g.user["role"] == "partner":
        sale_where = " WHERE s.partner_id=?"
        sale_params.append(g.partner["id"])
        commission_where = " WHERE c.partner_id=?"
        commission_params.append(g.partner["id"])
    sales = db.execute(
        """SELECT s.*,l.company_name,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') partner_name,
                  c.status commission_status,c.commission_amount_cents
           FROM sales s JOIN leads l ON l.id=s.lead_id JOIN partners p ON p.id=s.partner_id LEFT JOIN users u ON u.id=p.user_id
           LEFT JOIN commissions c ON c.sale_id=s.id""" + sale_where + " ORDER BY s.sale_date DESC,s.id DESC", sale_params
    ).fetchall()
    commissions = db.execute(
        """SELECT c.*,s.client_name,s.product_service,s.sale_date,
                  COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') partner_name,
                  COALESCE((SELECT SUM(sc.commission_change_cents) FROM sale_corrections sc WHERE sc.commission_id=c.id),0) correction_total_cents,
                  c.commission_amount_cents + COALESCE((SELECT SUM(sc.commission_change_cents) FROM sale_corrections sc WHERE sc.commission_id=c.id),0) adjusted_commission_cents
           FROM commissions c JOIN sales s ON s.id=c.sale_id JOIN partners p ON p.id=c.partner_id LEFT JOIN users u ON u.id=p.user_id""" + commission_where + " ORDER BY c.created_at DESC", commission_params
    ).fetchall()
    summary = {"PENDING": 0, "APPROVED": 0, "PAID": 0}
    for c in commissions:
        summary[c["status"]] = summary.get(c["status"], 0) + int(c["adjusted_commission_cents"] or 0)
    collected = sum(int(s["collected_cents"] or 0) for s in sales)
    return render_template(
        "money.html", title="Money", sales=sales, commissions=commissions, summary=summary,
        collected=collected, has_sales_data=bool(sales), has_commission_data=bool(commissions),
    )


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
    sql = """SELECT l.*,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name,
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
        partners = db.execute("""SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL ORDER BY u.full_name""").fetchall()
    if request.method == "POST":
        validate_csrf()
        owner_partner_id = g.partner["id"] if g.user["role"] == "partner" else request.form.get("owner_partner_id", type=int)
        data = {k: (request.form.get(k, "") or "").strip() for k in ["company_name","contact_name","email","phone","website","lead_source"]}
        initial_note = (request.form.get("summary_notes", "") or "").strip()
        errors = []
        if not owner_partner_id:
            errors.append("Choose a lead owner.")
        elif g.user["role"] == "admin" and not db.execute(
            "SELECT 1 FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL",
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
            return render_template("lead_form.html", title="Add Client", partners=partners, duplicate_matches=matches if g.user["role"]=="admin" else [])
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
    return render_template("lead_form.html", title="Add Client", partners=partners, duplicate_matches=[])


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
            """SELECT n.*,COALESCE(u.full_name,'Deleted Partner') author_name FROM lead_notes n LEFT JOIN users u ON u.id=n.author_user_id
               WHERE n.lead_id=? ORDER BY n.created_at DESC""", (lead_id,)
        ).fetchall()
        followups = db.execute(
            """SELECT f.*,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name FROM followups f
               JOIN partners p ON p.id=f.owner_partner_id LEFT JOIN users u ON u.id=p.user_id
               WHERE f.lead_id=? ORDER BY CASE f.status WHEN 'OPEN' THEN 0 ELSE 1 END, f.due_at""", (lead_id,)
        ).fetchall()
        activity = db.execute(
            "SELECT a.*,COALESCE(u.full_name,'System') actor_name FROM activity_log a LEFT JOIN users u ON u.id=a.actor_user_id WHERE a.entity_type='lead' AND a.entity_id=? ORDER BY a.created_at DESC LIMIT 20",
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
            """SELECT a.*,COALESCE(u.full_name,'System') actor_name FROM activity_log a
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
    client_message_count = 0
    if client_conversation:
        client_message_count = db.execute(
            "SELECT COUNT(*) c FROM client_messages WHERE conversation_id=?", (client_conversation["id"],)
        ).fetchone()["c"]
    partners = []
    if g.user["role"] == "admin":
        partners = db.execute("SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL ORDER BY u.full_name").fetchall()
    return render_template("lead_detail.html", title=lead["company_name"], lead=lead, notes=notes, followups=followups, sale=sale, activity=activity, pipeline=PIPELINE, partner_allowed=PARTNER_ALLOWED_STATUSES, partners=partners, now_input=local_now_input(), client_conversation=client_conversation, client_message_count=client_message_count)


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
    db.execute("INSERT INTO lead_notes(lead_id,author_user_id,body,created_at) VALUES (?,?,?,?)", (lead_id, g.user["id"], body[:4000], utcnow_iso()))
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
    authorized_lead(lead_id)
    new_partner = request.form.get("owner_partner_id", type=int)
    if not new_partner:
        abort(400)
    try:
        result = transfer_lead_ownership(lead_id, new_partner)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    if not result["changed"]:
        return redirect(url_for("main.lead_detail", lead_id=lead_id))
    log_activity(
        "LEAD_REASSIGNED", "lead", lead_id,
        "Lead and active client work moved to another Partner.",
        {"from_partner_id": result["old_partner_id"], "to_partner_id": result["new_partner_id"]},
    )
    get_db().commit()
    flash(f"Lead moved to {result['target_name']}.", "success")
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
    sql = """SELECT f.*,l.company_name,l.contact_name,l.owner_partner_id AS current_owner_partner_id,
                    COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name FROM followups f
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
        """SELECT s.*,l.company_name,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') partner_name,
                  c.status commission_status,c.commission_amount_cents
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
        """SELECT l.id,l.company_name,l.contact_name,l.owner_partner_id,u.full_name owner_name
           FROM leads l JOIN partners p ON p.id=l.owner_partner_id JOIN users u ON u.id=p.user_id
           LEFT JOIN sales s ON s.lead_id=l.id WHERE s.id IS NULL AND l.status!='LOST' ORDER BY l.last_activity_at DESC"""
    ).fetchall()
    lead = db.execute("""SELECT l.* FROM leads l LEFT JOIN sales s ON s.lead_id=l.id WHERE l.id=? AND s.id IS NULL AND l.status!='LOST'""", (lead_id,)).fetchone() if lead_id else None
    if request.method == "POST":
        validate_csrf()
        if not lead:
            flash("Choose a lead that does not already have a sale.", "error")
            return render_template("sale_form.html", title="Create Sale", leads=eligible, selected_lead_id=lead_id, today=today_str())
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
            errors.extend(validate_sale_amounts(deal, invoiced, collected, qualifying, payment_status))
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
            errors.extend(validate_sale_amounts(deal, invoiced, collected, qualifying, payment_status))
            if commission and commission["status"] != "PENDING":
                money_changed = any((
                    deal != sale["deal_amount_cents"],
                    invoiced != sale["invoiced_cents"],
                    collected != sale["collected_cents"],
                    qualifying != sale["qualifying_revenue_cents"],
                    payment_status != sale["payment_status"],
                ))
                if money_changed:
                    errors.append("Use Add Correction to change money details after approval.")
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
            flash("Sale updated. Commission updated.", "success")
            return redirect(url_for("main.sale_detail", sale_id=sale_id))
    sale = authorized_sale(sale_id)
    commission = db.execute("SELECT * FROM commissions WHERE sale_id=?", (sale_id,)).fetchone()
    corrections = db.execute(
        """SELECT sc.*,COALESCE(u.full_name,'System') actor_name FROM sale_corrections sc
           LEFT JOIN users u ON u.id=sc.created_by_user_id WHERE sc.sale_id=? ORDER BY sc.id DESC""",
        (sale_id,),
    ).fetchall()
    correction_total = sum(int(row["commission_change_cents"]) for row in corrections)
    adjusted_commission = max(0, int(commission["commission_amount_cents"]) + correction_total) if commission else 0
    activity = db.execute("SELECT a.*,COALESCE(u.full_name,'System') actor_name FROM activity_log a LEFT JOIN users u ON u.id=a.actor_user_id WHERE (a.entity_type='sale' AND a.entity_id=?) OR (a.entity_type='commission' AND a.entity_id=?) ORDER BY a.created_at DESC", (sale_id, commission["id"] if commission else -1)).fetchall()
    return render_template(
        "sale_detail.html", title=sale["client_name"], sale=sale, commission=commission,
        payment_statuses=PAYMENT_STATUSES, activity=activity, corrections=corrections,
        correction_total=correction_total, adjusted_commission=adjusted_commission,
    )


@bp.post("/sales/<int:sale_id>/corrections")
@admin_required
def sale_correction_add(sale_id: int):
    validate_csrf()
    sale = authorized_sale(sale_id)
    db = get_db()
    commission = db.execute("SELECT * FROM commissions WHERE sale_id=?", (sale_id,)).fetchone()
    if not commission or commission["status"] == "PENDING":
        flash("Edit the sale normally while the commission is pending.", "warning")
        return redirect(url_for("main.sale_detail", sale_id=sale_id))

    kinds = {"REFUND", "CHARGEBACK", "REVENUE_CORRECTION", "SALE_ADJUSTMENT", "COMMISSION_CORRECTION"}
    kind = (request.form.get("kind", "") or "").strip().upper()
    note = (request.form.get("note", "") or "").strip()
    payment_status = (request.form.get("payment_status", sale["payment_status"]) or "").upper()
    errors = []
    if kind not in kinds:
        errors.append("Choose a correction type.")
    if not note:
        errors.append("Add a short reason for this correction.")
    if payment_status not in PAYMENT_STATUSES:
        errors.append("Choose a valid payment status.")
    try:
        new_deal = money_to_cents(request.form.get("deal_amount"))
        new_invoiced = money_to_cents(request.form.get("amount_invoiced"))
        new_collected = money_to_cents(request.form.get("amount_collected"))
        new_qualifying = money_to_cents(request.form.get("qualifying_revenue"))
        errors.extend(validate_sale_amounts(
            new_deal, new_invoiced, new_collected, new_qualifying, payment_status,
        ))
    except ValueError as exc:
        errors.append(str(exc))
        new_deal = int(sale["deal_amount_cents"])
        new_invoiced = int(sale["invoiced_cents"])
        new_collected = int(sale["collected_cents"])
        new_qualifying = int(sale["qualifying_revenue_cents"])

    revenue_change = new_qualifying - int(sale["qualifying_revenue_cents"])
    if kind == "COMMISSION_CORRECTION":
        try:
            commission_change = signed_money_to_cents(request.form.get("commission_change"))
        except ValueError as exc:
            errors.append(str(exc))
            commission_change = 0
    else:
        commission_change = commission_change_for_revenue(revenue_change, int(commission["rate_bp_snapshot"]))

    prior_correction_total = db.execute(
        "SELECT COALESCE(SUM(commission_change_cents),0) c FROM sale_corrections WHERE commission_id=?",
        (commission["id"],),
    ).fetchone()["c"]
    resulting_commission = int(commission["commission_amount_cents"]) + int(prior_correction_total) + int(commission_change)
    if resulting_commission < 0:
        errors.append("This correction would make the commission less than zero.")
    no_money_change = all((
        new_deal == int(sale["deal_amount_cents"]),
        new_invoiced == int(sale["invoiced_cents"]),
        new_collected == int(sale["collected_cents"]),
        new_qualifying == int(sale["qualifying_revenue_cents"]),
        payment_status == sale["payment_status"],
    ))
    if no_money_change and commission_change == 0:
        errors.append("Nothing changed. Enter the corrected amounts.")
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("main.sale_detail", sale_id=sale_id))

    now = utcnow_iso()
    db.execute(
        """INSERT INTO sale_corrections(
               sale_id,commission_id,kind,old_deal_cents,new_deal_cents,old_invoiced_cents,new_invoiced_cents,
               old_collected_cents,new_collected_cents,old_qualifying_cents,new_qualifying_cents,
               commission_change_cents,note,created_by_user_id,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sale_id, commission["id"], kind, sale["deal_amount_cents"], new_deal,
         sale["invoiced_cents"], new_invoiced, sale["collected_cents"], new_collected,
         sale["qualifying_revenue_cents"], new_qualifying, commission_change, note[:2000], g.user["id"], now),
    )
    db.execute(
        """UPDATE sales SET deal_amount_cents=?,invoiced_cents=?,collected_cents=?,qualifying_revenue_cents=?,payment_status=?,updated_at=? WHERE id=?""",
        (new_deal, new_invoiced, new_collected, new_qualifying, payment_status, now, sale_id),
    )
    log_activity(
        "SALE_CORRECTION_ADDED", "sale", sale_id, "Sale correction added. Original commission history was kept.",
        {"kind": kind, "commission_change_cents": commission_change, "old_deal_cents": sale["deal_amount_cents"], "new_deal_cents": new_deal, "old_invoiced_cents": sale["invoiced_cents"], "new_invoiced_cents": new_invoiced, "old_qualifying_cents": sale["qualifying_revenue_cents"], "new_qualifying_cents": new_qualifying},
    )
    db.commit()
    flash("Correction saved. Original commission history was kept.", "success")
    return redirect(url_for("main.sale_detail", sale_id=sale_id))


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
        """SELECT c.*,s.client_name,s.product_service,s.sale_date,
                  COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') partner_name,
                  COALESCE((SELECT SUM(sc.commission_change_cents) FROM sale_corrections sc WHERE sc.commission_id=c.id),0) correction_total_cents,
                  c.commission_amount_cents + COALESCE((SELECT SUM(sc.commission_change_cents) FROM sale_corrections sc WHERE sc.commission_id=c.id),0) adjusted_commission_cents
           FROM commissions c JOIN sales s ON s.id=c.sale_id JOIN partners p ON p.id=c.partner_id LEFT JOIN users u ON u.id=p.user_id""" + where + " ORDER BY c.created_at DESC", params
    ).fetchall()
    summary = {}
    if g.user["role"] == "partner":
        has_commission_data = db.execute("SELECT COUNT(*) c FROM commissions WHERE partner_id=?", (g.partner["id"],)).fetchone()["c"] > 0
        for status in ["PENDING","APPROVED","PAID"]:
            summary[status] = db.execute(
                """SELECT COALESCE(SUM(c.commission_amount_cents + COALESCE((SELECT SUM(sc.commission_change_cents) FROM sale_corrections sc WHERE sc.commission_id=c.id),0)),0) c
                   FROM commissions c WHERE c.partner_id=? AND c.status=?""",
                (g.partner["id"], status),
            ).fetchone()["c"]
    else:
        has_commission_data = db.execute("SELECT COUNT(*) c FROM commissions").fetchone()["c"] > 0
        for status in ["PENDING","APPROVED","PAID"]:
            summary[status] = db.execute(
                """SELECT COALESCE(SUM(c.commission_amount_cents + COALESCE((SELECT SUM(sc.commission_change_cents) FROM sale_corrections sc WHERE sc.commission_id=c.id),0)),0) c
                   FROM commissions c WHERE c.status=?""",
                (status,),
            ).fetchone()["c"]
    return render_template("commissions.html", title="Commissions", commissions=rows, summary=summary, has_commission_data=has_commission_data)


@bp.post("/commissions/<int:commission_id>/adjust")
@admin_required
def commission_adjust(commission_id: int):
    validate_csrf()
    commission = authorized_commission(commission_id)
    if commission["status"] != "PENDING":
        flash("Only pending commissions can be changed.", "error")
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
        flash("Only approved commissions can be marked as paid.", "error")
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
    rows = db.execute(
        """SELECT p.id,p.user_id,p.commission_stage_id,p.phone,p.notes,p.joined_at,p.account_deleted_at,
                  u.full_name,u.created_at,cs.name commission_stage_name,cs.rate_bp commission_rate_bp
           FROM partners p
           JOIN users u ON u.id=p.user_id
           JOIN commission_stages cs ON cs.id=p.commission_stage_id
           WHERE p.account_deleted_at IS NULL
           ORDER BY lower(u.full_name),p.id"""
    ).fetchall()
    return render_template("partners_list.html", title="Partners", partners=rows)


@bp.route("/admin/partners/new", methods=["GET", "POST"])
@admin_required
def partner_new():
    db = get_db()
    stages = db.execute("SELECT * FROM commission_stages WHERE active=1 ORDER BY sort_order").fetchall()
    if request.method == "POST":
        validate_csrf()
        full_name = _clean_account_name(request.form.get("full_name", ""))
        password = request.form.get("partner_password", "") or ""
        phone = (request.form.get("phone", "") or "").strip()
        notes = (request.form.get("notes", "") or "").strip()
        stage_id = request.form.get("commission_stage_id", type=int)
        stage = db.execute("SELECT * FROM commission_stages WHERE id=? AND active=1", (stage_id,)).fetchone()
        errors = []
        if len(full_name) < 2:
            errors.append("Enter the Partner name.")
        elif _account_name_in_use(db, full_name):
            errors.append("This name is already in use.")
        if password == "":
            errors.append("Enter the Partner password.")
        if not stage:
            errors.append("Choose a commission level.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("partner_form.html", title="Create Partner", stages=stages)
        now = utcnow_iso()
        internal_email = _new_internal_account_email(db)
        try:
            cur = db.execute(
                """INSERT INTO users(full_name,email,password_hash,role,active,force_password_change,created_at,updated_at)
                   VALUES (?,?,?,'partner',1,0,?,?)""",
                (full_name, internal_email, hash_password(password), now, now),
            )
            user_id = cur.lastrowid
            vault_store_password(db, user_id, password)
            cur = db.execute(
                """INSERT INTO partners(user_id,commission_stage_id,phone,notes,joined_at,active,account_deleted_at,historical_name)
                   VALUES (?,?,?,?,?,1,NULL,?)""",
                (user_id, stage_id, phone[:60], notes[:2000], now, full_name),
            )
            partner_id = cur.lastrowid
        except (sqlite3.IntegrityError, IntegrityError):
            db.rollback()
            flash("This name is already in use.", "error")
            return render_template("partner_form.html", title="Create Partner", stages=stages)
        log_activity(
            "PARTNER_CREATED",
            "partner",
            partner_id,
            "Partner account created.",
            {"stage": stage["name"], "rate_bp": stage["rate_bp"]},
        )
        db.commit()
        return render_template(
            "partner_created.html",
            title="Partner Created",
            partner={"id": partner_id, "full_name": full_name},
            chosen_password=password,
        )
    return render_template("partner_form.html", title="Create Partner", stages=stages)


@bp.route("/admin/partners/<int:partner_id>", methods=["GET", "POST"])
@admin_required
def partner_detail(partner_id: int):
    db = get_db()
    partner = db.execute(
        """SELECT p.*,u.full_name,u.created_at,cs.name commission_stage_name,cs.rate_bp commission_rate_bp
           FROM partners p
           JOIN users u ON u.id=p.user_id
           JOIN commission_stages cs ON cs.id=p.commission_stage_id
           WHERE p.id=? AND p.account_deleted_at IS NULL""",
        (partner_id,),
    ).fetchone()
    if not partner:
        abort(404)
    stages = db.execute("SELECT * FROM commission_stages WHERE active=1 ORDER BY sort_order").fetchall()
    if request.method == "POST":
        validate_csrf()
        full_name = _clean_account_name(request.form.get("full_name", ""))
        phone = (request.form.get("phone", "") or "").strip()
        notes = (request.form.get("notes", "") or "").strip()
        stage_id = request.form.get("commission_stage_id", type=int)
        stage = db.execute("SELECT * FROM commission_stages WHERE id=? AND active=1", (stage_id,)).fetchone()
        errors = []
        if len(full_name) < 2:
            errors.append("Enter the Partner name.")
        elif _account_name_in_use(db, full_name, int(partner["user_id"])):
            errors.append("This name is already in use.")
        if not stage:
            errors.append("Choose a commission level.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("partner_detail.html", title=partner["full_name"], partner=partner, stages=stages)
        if stage_id != partner["commission_stage_id"]:
            log_activity(
                "PARTNER_COMMISSION_RATE_CHANGED",
                "partner",
                partner_id,
                "Partner commission level changed.",
                {"from": partner["commission_stage_name"], "from_rate_bp": partner["commission_rate_bp"], "to": stage["name"], "to_rate_bp": stage["rate_bp"]},
            )
        if full_name != partner["full_name"] or phone[:60] != partner["phone"] or notes[:2000] != partner["notes"]:
            log_activity("PARTNER_UPDATED", "partner", partner_id, "Partner details updated.")
        try:
            db.execute(
                "UPDATE users SET full_name=?,updated_at=? WHERE id=?",
                (full_name, utcnow_iso(), partner["user_id"]),
            )
            db.execute(
                "UPDATE partners SET commission_stage_id=?,phone=?,notes=?,historical_name=? WHERE id=?",
                (stage_id, phone[:60], notes[:2000], full_name, partner_id),
            )
            db.commit()
        except (sqlite3.IntegrityError, IntegrityError):
            db.rollback()
            flash("This name is already in use.", "error")
            return redirect(url_for("main.partner_detail", partner_id=partner_id))
        flash("Partner saved. Old commissions stay the same.", "success")
        return redirect(url_for("main.partner_detail", partner_id=partner_id))
    return render_template("partner_detail.html", title=partner["full_name"], partner=partner, stages=stages)


@bp.post("/admin/partners/<int:partner_id>/reset-password")
@admin_required
def partner_reset_password(partner_id: int):
    validate_csrf()
    password = request.form.get("partner_password", "") or ""
    confirm_password = request.form.get("confirm_partner_password", "") or ""
    if not valid_password(password):
        flash("Enter the new Partner password you want to use.", "error")
        return redirect(url_for("main.account_security", _anchor=f"partner-{partner_id}"))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("main.account_security", _anchor=f"partner-{partner_id}"))
    db = get_db()
    partner = db.execute(
        """SELECT p.id,p.user_id,u.full_name
           FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.id=? AND p.account_deleted_at IS NULL AND u.active=1""",
        (partner_id,),
    ).fetchone()
    if not partner:
        abort(404)
    db.execute(
        """UPDATE users
           SET password_hash=?,force_password_change=0,failed_login_count=0,locked_until=NULL,updated_at=?
           WHERE id=?""",
        (hash_password(password), utcnow_iso(), partner["user_id"]),
    )
    vault_store_password(db, partner["user_id"], password)
    log_activity("PARTNER_PASSWORD_RESET", "partner", partner_id, "Partner password changed from Account & Security.")
    db.commit()
    founder, partners = _account_security_context(db)
    flash(f"Password changed for {partner['full_name']}.", "success")
    return render_template(
        "account_security.html",
        title="Account & Security",
        founder=founder,
        partners=partners,
    )


@bp.post("/admin/partners/<int:partner_id>/delete")
@admin_required
def partner_delete(partner_id: int):
    validate_csrf()
    if request.form.get("confirm_delete") != "1":
        abort(400, description="Confirm Partner deletion.")
    db = get_db()
    partner = db.execute(
        """SELECT p.*,u.full_name,u.avatar_stored_name
           FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.id=? AND p.account_deleted_at IS NULL""",
        (partner_id,),
    ).fetchone()
    if not partner:
        abort(404)

    active_leads = db.execute(
        """SELECT DISTINCT l.id FROM leads l
           LEFT JOIN followups f ON f.lead_id=l.id AND f.status='OPEN'
           LEFT JOIN client_conversations c ON c.lead_id=l.id AND c.status='ACTIVE'
           LEFT JOIN website_inquiries w ON w.lead_id=l.id AND w.status='CLAIMED'
           WHERE l.owner_partner_id=? AND (l.status NOT IN ('WON','LOST') OR f.id IS NOT NULL OR c.id IS NOT NULL OR w.id IS NOT NULL)
           ORDER BY l.id""",
        (partner_id,),
    ).fetchall()
    extra_active_conversations = db.execute(
        "SELECT id FROM client_conversations WHERE owner_partner_id=? AND status='ACTIVE' AND lead_id IS NULL",
        (partner_id,),
    ).fetchall()
    extra_claimed_inquiries = db.execute(
        "SELECT id FROM website_inquiries WHERE claimed_by_partner_id=? AND status='CLAIMED' AND lead_id IS NULL",
        (partner_id,),
    ).fetchall()
    has_active_work = bool(active_leads or extra_active_conversations or extra_claimed_inquiries)
    replacement_partner_id = request.form.get("move_active_to_partner_id", type=int)
    replacement = None
    if has_active_work:
        if not replacement_partner_id or replacement_partner_id == partner_id:
            flash("This Partner still has active work. Choose another Partner to receive it first.", "error")
            return redirect(url_for("main.account_security", _anchor=f"partner-{partner_id}"))
        replacement = db.execute(
            """SELECT p.id,p.user_id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id
               WHERE p.id=? AND p.id<>? AND p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL""",
            (replacement_partner_id, partner_id),
        ).fetchone()
        if not replacement:
            flash("Choose an active Partner to receive the work.", "error")
            return redirect(url_for("main.account_security", _anchor=f"partner-{partner_id}"))

    now = utcnow_iso()
    old_avatar = partner["avatar_stored_name"]
    user_id = int(partner["user_id"])
    try:
        if replacement:
            for row in active_leads:
                result = transfer_lead_ownership(int(row["id"]), int(replacement["id"]), allow_sale_history=True)
                if result["changed"]:
                    log_activity(
                        "LEAD_REASSIGNED_BEFORE_PARTNER_DELETE", "lead", int(row["id"]),
                        "Active work moved before Partner account deletion.",
                        {"from_partner_id": partner_id, "to_partner_id": int(replacement["id"])},
                    )
            # Handle rare active client records that are not linked to a Lead.
            db.execute(
                "UPDATE client_conversations SET owner_partner_id=?,updated_at=? WHERE owner_partner_id=? AND status='ACTIVE' AND lead_id IS NULL",
                (replacement["id"], now, partner_id),
            )
            db.execute(
                "UPDATE website_inquiries SET claimed_by_partner_id=?,updated_at=? WHERE claimed_by_partner_id=? AND status='CLAIMED' AND lead_id IS NULL",
                (replacement["id"], now, partner_id),
            )

        # Keep the Partner ID as business history, but remove the login/profile.
        db.execute(
            """UPDATE partners
               SET historical_name=?,user_id=NULL,phone='',notes='',active=0,account_deleted_at=?
               WHERE id=?""",
            (partner["full_name"][:160], now, partner_id),
        )

        # Detach user references that are history, then remove the login account.
        for table, column in (
            ("leads", "created_by_user_id"),
            ("lead_notes", "author_user_id"),
            ("followups", "created_by_user_id"),
            ("sales", "created_by_user_id"),
            ("resources", "created_by_user_id"),
            ("messages", "sender_user_id"),
            ("voice_calls", "started_by_user_id"),
            ("voice_calls", "ended_by_user_id"),
            ("voice_call_signals", "sender_user_id"),
            ("duplicate_claims", "resolved_by_user_id"),
            ("activity_log", "actor_user_id"),
            ("settings", "updated_by_user_id"),
            ("client_messages", "sent_by_user_id"),
            ("sale_corrections", "created_by_user_id"),
        ):
            try:
                db.execute(f'UPDATE "{table}" SET "{column}"=NULL WHERE "{column}"=?', (user_id,))
            except Exception:
                # sale_corrections does not exist on pre-V15 databases until bootstrap runs.
                if table != "sale_corrections":
                    raise
        db.execute("DELETE FROM client_notifications WHERE user_id=?", (user_id,))
        deleted = db.execute("DELETE FROM users WHERE id=? AND role='partner'", (user_id,))
        if deleted.rowcount != 1:
            raise RuntimeError("Partner account deletion did not remove exactly one login account.")

        log_activity(
            "PARTNER_DELETED", "partner", partner_id,
            "Partner account deleted. Business history was kept.",
            {"partner_name": partner["full_name"], "active_work_moved_to": int(replacement["id"]) if replacement else None},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    if old_avatar:
        try:
            (_profile_picture_dir() / Path(old_avatar).name).unlink(missing_ok=True)
        except OSError:
            pass
    if replacement:
        flash(f"Partner deleted. Active work moved to {replacement['full_name']}. Business history was kept.", "success")
    else:
        flash("Partner deleted. Business history was kept.", "success")
    return redirect(url_for("main.account_security"))


@bp.route("/admin/duplicates")
@admin_required
def duplicate_claims():
    db = get_db()
    claims = db.execute("""SELECT d.*,
        COALESCE(claimant.full_name,NULLIF(cp.historical_name,''),'Deleted Partner') claimant_name,
        COALESCE(owner.full_name,NULLIF(op.historical_name,''),'Deleted Partner') owner_name,l.company_name matched_company
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
            "SELECT 1 FROM partners p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL",
            (new_owner,),
        ).fetchone()
        if not target:
            flash("That Partner is not available. Keep the current owner or choose another Partner.", "error")
            return redirect(url_for("main.duplicate_claims"))
        try:
            result = transfer_lead_ownership(lead["id"], new_owner)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.duplicate_claims"))
        status = "REASSIGNED"
        log_activity(
            "OWNERSHIP_OVERRIDDEN", "lead", lead["id"],
            "Lead and active client work moved after duplicate review.",
            {"from_partner_id": old_owner, "to_partner_id": result["new_partner_id"], "duplicate_claim_id": claim_id},
        )
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
        """SELECT m.id,m.partner_id,m.sender_user_id,m.body,m.created_at,
                  COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted account') AS sender_name
           FROM messages m JOIN partners p ON p.id=m.partner_id LEFT JOIN users u ON u.id=m.sender_user_id
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
    partner = authorized_conversation_partner(partner_id)
    if partner["account_deleted_at"]:
        abort(410)
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
    if partner["account_deleted_at"]:
        return jsonify({"ok": False, "error": "This Partner has been deleted."}), 410
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
    rows = db.execute("""SELECT a.*,COALESCE(u.full_name,'System') actor_name FROM activity_log a
                        LEFT JOIN users u ON u.id=a.actor_user_id ORDER BY a.created_at DESC LIMIT 500""").fetchall()
    return render_template("activity.html", title="Activity", activities=rows)


def _account_security_context(db):
    founder = db.execute(
        """SELECT id,full_name,created_at,updated_at
           FROM users WHERE id=? AND role='admin' AND active=1""",
        (g.user["id"],),
    ).fetchone()
    if not founder:
        abort(403)
    partners = db.execute(
        """SELECT p.id,p.user_id,u.full_name,u.created_at,
                  cs.name commission_stage_name,cs.rate_bp commission_rate_bp,
                  ((SELECT COUNT(*) FROM leads l WHERE l.owner_partner_id=p.id AND l.status NOT IN ('WON','LOST')) +
                   (SELECT COUNT(*) FROM followups f WHERE f.owner_partner_id=p.id AND f.status='OPEN') +
                   (SELECT COUNT(*) FROM client_conversations c WHERE c.owner_partner_id=p.id AND c.status='ACTIVE') +
                   (SELECT COUNT(*) FROM website_inquiries w WHERE w.claimed_by_partner_id=p.id AND w.status='CLAIMED')) AS active_work_count
           FROM partners p
           JOIN users u ON u.id=p.user_id
           JOIN commission_stages cs ON cs.id=p.commission_stage_id
           WHERE p.account_deleted_at IS NULL AND u.active=1
           ORDER BY lower(u.full_name),p.id"""
    ).fetchall()
    return founder, partners


@bp.get("/admin/settings/account-security")
@admin_required
def account_security():
    db = get_db()
    founder, partners = _account_security_context(db)
    return render_template(
        "account_security.html",
        title="Account & Security",
        founder=founder,
        partners=partners,
    )


@bp.post("/admin/settings/account-security/reveal-password")
@admin_required
def account_security_reveal_password():
    validate_csrf()
    try:
        user_id = int(request.form.get("user_id", "0"))
    except (TypeError, ValueError):
        abort(400)
    db = get_db()
    target = db.execute(
        """SELECT u.id,u.full_name,u.role
           FROM users u
           LEFT JOIN partners p ON p.user_id=u.id
           WHERE u.id=? AND u.active=1
             AND (u.role='admin' OR (u.role='partner' AND p.account_deleted_at IS NULL))
           LIMIT 1""",
        (user_id,),
    ).fetchone()
    if not target or target["role"] not in {"admin", "partner"}:
        abort(404)
    if target["role"] == "admin" and target["id"] != g.user["id"]:
        abort(403)
    password = vault_current_password(db, user_id)
    if password is None:
        return jsonify({"ok": False, "error": "This account is not initialized for Founder password visibility yet. Change/reset its password once, or run the password visibility initializer."}), 404
    log_activity("ACCOUNT_PASSWORD_REVEALED", "user", user_id, f"Founder revealed current {target['role']} account password from Account & Security.")
    db.commit()
    response = jsonify({"ok": True, "password": password})
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@bp.post("/admin/settings/account-security/founder-password")
@admin_required
def founder_password_change():
    validate_csrf()
    new_password = request.form.get("new_password", "") or ""
    confirm_password = request.form.get("confirm_password", "") or ""
    if not valid_password(new_password):
        flash("Enter the new Founder password you want to use.", "error")
        return redirect(url_for("main.account_security"))
    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("main.account_security"))
    db = get_db()
    db.execute(
        """UPDATE users
           SET password_hash=?,force_password_change=0,failed_login_count=0,locked_until=NULL,updated_at=?
           WHERE id=? AND role='admin'""",
        (hash_password(new_password), utcnow_iso(), g.user["id"]),
    )
    vault_store_password(db, g.user["id"], new_password)
    log_activity("FOUNDER_PASSWORD_CHANGED", "user", g.user["id"], "Founder password changed from Account & Security.")
    db.commit()
    refreshed = db.execute("SELECT * FROM users WHERE id=? AND role='admin'", (g.user["id"],)).fetchone()
    if not refreshed:
        abort(403)
    login_user(refreshed)
    if not current_app.testing:
        try:
            from config import BASE_DIR
            first_access = BASE_DIR / "FIRST_RUN_FOUNDER_ACCESS.txt"
            if first_access.exists():
                first_access.unlink()
        except OSError:
            pass
    founder, partners = _account_security_context(db)
    flash("Founder password changed successfully. Other Founder sessions were signed out.", "success")
    return render_template(
        "account_security.html",
        title="Account & Security",
        founder=founder,
        partners=partners,
    )


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
    from .gmail_ops import connection_status as gmail_connection_status
    from .calendar_ops import connection_status as calendar_connection_status
    return render_template(
        "settings.html",
        title="Settings",
        stages=stages,
        company_name=setting("company_name","Realty Systems Foundry"),
        currency_code=setting("currency_code","USD"),
        gmail_status=gmail_connection_status(),
        calendar_status=calendar_connection_status(),
    )


@bp.get("/admin/settings/gmail/connect")
@admin_required
def gmail_connect():
    from .gmail_ops import build_authorization_url
    redirect_uri = current_app.config.get("GMAIL_OAUTH_REDIRECT_URI", "").strip()
    if not redirect_uri:
        flash("Gmail OAuth redirect URI is not configured yet.", "error")
        return redirect(url_for("main.settings"))
    try:
        authorization_url = build_authorization_url(redirect_uri)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.settings"))
    return redirect(authorization_url)


@bp.get("/admin/settings/gmail/callback")
@admin_required
def gmail_callback():
    from .gmail_ops import complete_authorization, validate_oauth_state
    if request.args.get("error"):
        flash("Google Gmail authorization was cancelled or denied.", "warning")
        return redirect(url_for("main.settings"))
    redirect_uri = current_app.config.get("GMAIL_OAUTH_REDIRECT_URI", "").strip()
    try:
        validate_oauth_state(request.args.get("state", ""))
        email_address = complete_authorization(request.args.get("code", ""), redirect_uri)
    except RuntimeError as exc:
        current_app.logger.warning("Gmail OAuth connection failed: %s", exc)
        flash(str(exc), "error")
        return redirect(url_for("main.settings"))
    log_activity("GMAIL_CONNECTED", "settings", None, f"Gmail API connected for {email_address}.")
    flash(f"Gmail connected: {email_address}", "success")
    return redirect(url_for("main.settings"))


@bp.post("/admin/settings/gmail/verify")
@admin_required
def gmail_verify():
    validate_csrf()
    from .gmail_ops import verify_connection
    try:
        profile = verify_connection()
    except RuntimeError as exc:
        flash(str(exc), "error")
    else:
        flash(f"Gmail connection verified: {profile.get('emailAddress','')}", "success")
    return redirect(url_for("main.settings"))


@bp.get("/admin/settings/calendar/connect")
@admin_required
def calendar_connect():
    from .calendar_ops import build_authorization_url
    redirect_uri = current_app.config.get("GOOGLE_CALENDAR_OAUTH_REDIRECT_URI", "").strip()
    if not redirect_uri:
        flash("Google Calendar OAuth redirect URI is not configured yet.", "error")
        return redirect(url_for("main.settings"))
    try:
        authorization_url = build_authorization_url(redirect_uri)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.settings"))
    return redirect(authorization_url)


@bp.get("/admin/settings/calendar/callback")
@admin_required
def calendar_callback():
    from .calendar_ops import complete_authorization, validate_oauth_state
    if request.args.get("error"):
        flash("Google Calendar authorization was cancelled or denied.", "warning")
        return redirect(url_for("main.settings"))
    redirect_uri = current_app.config.get("GOOGLE_CALENDAR_OAUTH_REDIRECT_URI", "").strip()
    try:
        validate_oauth_state(request.args.get("state", ""))
        complete_authorization(request.args.get("code", ""), redirect_uri)
    except RuntimeError as exc:
        current_app.logger.warning("Google Calendar OAuth connection failed: %s", exc)
        flash(str(exc), "error")
        return redirect(url_for("main.settings"))
    log_activity("GOOGLE_CALENDAR_CONNECTED", "settings", None, "Google Calendar connected for Deal demo scheduling.")
    flash("Google Calendar connected.", "success")
    return redirect(url_for("main.settings"))


@bp.post("/admin/settings/calendar/verify")
@admin_required
def calendar_verify():
    validate_csrf()
    from .calendar_ops import verify_connection
    try:
        verify_connection()
    except RuntimeError as exc:
        flash(str(exc), "error")
    else:
        flash("Google Calendar connection verified.", "success")
    return redirect(url_for("main.settings"))


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
            flash("Founder password controls are in Settings → Account & Security.", "success")
            return redirect(url_for("main.account_security"))
        else:
            if g.user["role"] != "admin":
                abort(403)
            full_name = _clean_account_name(request.form.get("full_name", ""))
            if len(full_name) < 2:
                flash("Enter your name.", "error")
            elif _account_name_in_use(db, full_name, int(g.user["id"])):
                flash("This name is already in use.", "error")
            else:
                try:
                    db.execute("UPDATE users SET full_name=?,updated_at=? WHERE id=?", (full_name, utcnow_iso(), g.user["id"]))
                    log_activity("PROFILE_UPDATED", "user", g.user["id"], "Profile updated.")
                    db.commit()
                    flash("Profile saved.", "success")
                    return redirect(url_for("main.profile"))
                except (sqlite3.IntegrityError, IntegrityError):
                    db.rollback()
                    flash("This name is already in use.", "error")
    return render_template("profile.html", title="Profile")

# ---------------------------------------------------------------------------
# Unified website inquiry + client conversation workspace
# ---------------------------------------------------------------------------

def _authorized_inquiry(inquiry_id: int, allow_unclaimed: bool = True):
    db = get_db()
    row = db.execute(
        """SELECT i.*,COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') claimed_by_name
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
                  COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name
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


@bp.post("/communications/manual-note")
@login_required
def communication_manual_note():
    validate_csrf()
    body = (request.form.get("body", "") or "").strip()[:3000]
    if not body:
        return jsonify({"ok": False, "error": "validation", "message": "Write a manual note first."}), 400

    prospect_id = request.form.get("prospect_id", type=int)
    inquiry_id = request.form.get("inquiry_id", type=int)
    deal_id = request.form.get("deal_id", type=int)
    supplied = [value for value in (prospect_id, inquiry_id, deal_id) if value is not None]
    if len(supplied) != 1:
        return jsonify({"ok": False, "error": "validation", "message": "Choose one communication record."}), 400

    db = get_db()
    journey_source = "OUTBOUND"

    if deal_id is not None:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id FROM deals WHERE id=?",
            (deal_id,),
        ).fetchone()
        if not deal:
            return jsonify({"ok": False, "error": "not_found", "message": "Deal not found."}), 404
        prospect_id = int(deal["prospect_id"]) if deal["prospect_id"] is not None else None
        inquiry_id = int(deal["website_inquiry_id"]) if deal["website_inquiry_id"] is not None else None
        if inquiry_id is not None:
            _authorized_inquiry(inquiry_id)
            journey_source = "INBOUND"
    elif prospect_id is not None:
        prospect = db.execute("SELECT id FROM prospects WHERE id=?", (prospect_id,)).fetchone()
        if not prospect:
            return jsonify({"ok": False, "error": "not_found", "message": "Prospect not found."}), 404
        linked = db.execute(
            "SELECT id,website_inquiry_id FROM deals WHERE prospect_id=? LIMIT 1",
            (prospect_id,),
        ).fetchone()
        if linked:
            deal_id = int(linked["id"])
            inquiry_id = int(linked["website_inquiry_id"]) if linked["website_inquiry_id"] is not None else None
    else:
        _authorized_inquiry(inquiry_id)
        journey_source = "INBOUND"
        linked = db.execute(
            "SELECT id,prospect_id FROM deals WHERE website_inquiry_id=? LIMIT 1",
            (inquiry_id,),
        ).fetchone()
        if linked:
            deal_id = int(linked["id"])
            prospect_id = int(linked["prospect_id"]) if linked["prospect_id"] is not None else None

    now = utcnow_iso()
    cur = db.execute(
        """INSERT INTO communication_notes(
               prospect_id,website_inquiry_id,deal_id,journey_source,body,created_by_user_id,created_at
           ) VALUES (?,?,?,?,?,?,?)""",
        (prospect_id, inquiry_id, deal_id, journey_source, body, g.user["id"], now),
    )
    note_id = int(cur.lastrowid)
    db.commit()
    return jsonify({
        "ok": True,
        "message": "Manual note saved.",
        "entry": {
            "id": f"manual-note-{note_id}",
            "at": now,
            "source": journey_source,
            "channel": "NOTE",
            "direction": "RSF",
            "body": body,
        },
    })


def _authorized_communication_note(note_id: int):
    db = get_db()
    note = db.execute(
        """SELECT id,prospect_id,website_inquiry_id,deal_id,journey_source,body,
                  created_by_user_id,created_at
           FROM communication_notes
           WHERE id=?""",
        (note_id,),
    ).fetchone()
    if not note:
        abort(404)

    inquiry_id = int(note["website_inquiry_id"]) if note["website_inquiry_id"] is not None else None
    if inquiry_id is None and note["deal_id"] is not None:
        deal = db.execute(
            "SELECT website_inquiry_id FROM deals WHERE id=?",
            (note["deal_id"],),
        ).fetchone()
        if deal and deal["website_inquiry_id"] is not None:
            inquiry_id = int(deal["website_inquiry_id"])
    if inquiry_id is not None:
        _authorized_inquiry(inquiry_id)
    return note


def _set_legacy_notes_after_conversation(db, source_type: str, source_id: int, value: str) -> None:
    source_type = (source_type or "").strip().lower()
    now = utcnow_iso()

    if source_type == "prospect":
        prospect = db.execute("SELECT id FROM prospects WHERE id=?", (source_id,)).fetchone()
        if not prospect:
            abort(404)
        db.execute(
            "UPDATE prospects SET notes_after_conversation=?,updated_at=? WHERE id=?",
            (value, now, source_id),
        )
        db.execute(
            "UPDATE deals SET notes_after_conversation=?,updated_at=? WHERE prospect_id=?",
            (value, now, source_id),
        )
        db.execute(
            """UPDATE website_inquiries
               SET notes_after_conversation=?,updated_at=?
               WHERE id IN (
                 SELECT website_inquiry_id FROM deals
                 WHERE prospect_id=? AND website_inquiry_id IS NOT NULL
               )""",
            (value, now, source_id),
        )
        return

    if source_type == "inquiry":
        _authorized_inquiry(source_id)
        db.execute(
            "UPDATE website_inquiries SET notes_after_conversation=?,updated_at=? WHERE id=?",
            (value, now, source_id),
        )
        db.execute(
            "UPDATE deals SET notes_after_conversation=?,updated_at=? WHERE website_inquiry_id=?",
            (value, now, source_id),
        )
        db.execute(
            """UPDATE prospects
               SET notes_after_conversation=?,updated_at=?
               WHERE id IN (
                 SELECT prospect_id FROM deals
                 WHERE website_inquiry_id=? AND prospect_id IS NOT NULL
               )""",
            (value, now, source_id),
        )
        return

    if source_type == "deal":
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id FROM deals WHERE id=?",
            (source_id,),
        ).fetchone()
        if not deal:
            abort(404)
        if deal["website_inquiry_id"] is not None:
            _authorized_inquiry(int(deal["website_inquiry_id"]))
        db.execute(
            "UPDATE deals SET notes_after_conversation=?,updated_at=? WHERE id=?",
            (value, now, source_id),
        )
        if deal["prospect_id"] is not None:
            db.execute(
                "UPDATE prospects SET notes_after_conversation=?,updated_at=? WHERE id=?",
                (value, now, int(deal["prospect_id"])),
            )
        if deal["website_inquiry_id"] is not None:
            db.execute(
                "UPDATE website_inquiries SET notes_after_conversation=?,updated_at=? WHERE id=?",
                (value, now, int(deal["website_inquiry_id"])),
            )
        return

    abort(400)


@bp.post("/communications/note-entry/update")
@login_required
def communication_note_entry_update():
    validate_csrf()
    kind = (request.form.get("kind", "") or "").strip().lower()
    body = (request.form.get("body", "") or "").strip()[:3000]
    if not body:
        return jsonify({"ok": False, "error": "validation", "message": "A saved note cannot be empty. Delete it instead."}), 400

    db = get_db()
    if kind == "manual":
        note_id = request.form.get("note_id", type=int)
        if not note_id:
            return jsonify({"ok": False, "error": "validation", "message": "Manual note is missing."}), 400
        _authorized_communication_note(note_id)
        db.execute("UPDATE communication_notes SET body=? WHERE id=?", (body, note_id))
    elif kind == "legacy":
        source_type = (request.form.get("source_type", "") or "").strip().lower()
        source_id = request.form.get("source_id", type=int)
        if not source_id:
            return jsonify({"ok": False, "error": "validation", "message": "Note source is missing."}), 400
        _set_legacy_notes_after_conversation(db, source_type, source_id, body)
    else:
        return jsonify({"ok": False, "error": "validation", "message": "Unsupported note type."}), 400

    db.commit()
    return jsonify({"ok": True, "body": body, "message": "Note updated."})


@bp.post("/communications/note-entry/delete")
@login_required
def communication_note_entry_delete():
    validate_csrf()
    kind = (request.form.get("kind", "") or "").strip().lower()
    db = get_db()

    if kind == "manual":
        note_id = request.form.get("note_id", type=int)
        if not note_id:
            return jsonify({"ok": False, "error": "validation", "message": "Manual note is missing."}), 400
        _authorized_communication_note(note_id)
        db.execute("DELETE FROM communication_notes WHERE id=?", (note_id,))
    elif kind == "legacy":
        source_type = (request.form.get("source_type", "") or "").strip().lower()
        source_id = request.form.get("source_id", type=int)
        if not source_id:
            return jsonify({"ok": False, "error": "validation", "message": "Note source is missing."}), 400
        _set_legacy_notes_after_conversation(db, source_type, source_id, "")
    else:
        return jsonify({"ok": False, "error": "validation", "message": "Unsupported note type."}), 400

    db.commit()
    return jsonify({"ok": True, "message": "Note deleted."})



def _communication_context_ids(*, prospect_id: int | None = None, inquiry_id: int | None = None, deal_id: int | None = None):
    """Resolve one linked client journey without creating duplicate conversations."""
    db = get_db()
    deal = None
    if deal_id:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id FROM deals WHERE id=?",
            (deal_id,),
        ).fetchone()
        if not deal:
            abort(404)
        prospect_id = int(deal["prospect_id"]) if deal["prospect_id"] is not None else prospect_id
        inquiry_id = int(deal["website_inquiry_id"]) if deal["website_inquiry_id"] is not None else inquiry_id
    if inquiry_id:
        _authorized_inquiry(inquiry_id)
    if prospect_id:
        row = db.execute("SELECT id FROM prospects WHERE id=?", (prospect_id,)).fetchone()
        if not row:
            abort(404)
    return prospect_id, inquiry_id, deal_id


def _communication_conversation_id(*, prospect_id: int | None = None, inquiry_id: int | None = None,
                                   deal_id: int | None = None, create: bool = False) -> int | None:
    db = get_db()
    prospect_id, inquiry_id, deal_id = _communication_context_ids(
        prospect_id=prospect_id, inquiry_id=inquiry_id, deal_id=deal_id
    )

    # A merged Prospect + Website journey always collapses to one canonical thread.
    if prospect_id and create:
        from .client_ops import ensure_prospect_conversation
        try:
            return int(ensure_prospect_conversation(prospect_id, owner_partner_id=partner_scope_id()))
        except ValueError:
            pass

    if inquiry_id:
        inquiry = db.execute(
            "SELECT client_conversation_id FROM website_inquiries WHERE id=?",
            (inquiry_id,),
        ).fetchone()
        if inquiry and inquiry["client_conversation_id"]:
            return int(inquiry["client_conversation_id"])

    if prospect_id:
        row = db.execute(
            "SELECT id FROM client_conversations WHERE prospect_id=? AND status='ACTIVE' ORDER BY id DESC LIMIT 1",
            (prospect_id,),
        ).fetchone()
        if row:
            return int(row["id"])
        if create:
            from .client_ops import ensure_prospect_conversation
            return int(ensure_prospect_conversation(prospect_id, owner_partner_id=partner_scope_id()))
    return None


@bp.get("/communications/email-thread")
@login_required
def communication_email_thread():
    prospect_id = request.args.get("prospect_id", type=int)
    inquiry_id = request.args.get("inquiry_id", type=int)
    deal_id = request.args.get("deal_id", type=int)
    conversation_id = _communication_conversation_id(
        prospect_id=prospect_id, inquiry_id=inquiry_id, deal_id=deal_id, create=True
    )
    if not conversation_id:
        return jsonify({"ok": False, "message": "No email conversation is available for this client."}), 404

    conv = _authorized_client_conversation(conversation_id)
    db = get_db()
    rows = db.execute(
        """SELECT m.*,u.full_name sent_by_name
           FROM client_messages m
           LEFT JOIN users u ON u.id=m.sent_by_user_id
           WHERE m.conversation_id=? AND m.channel='EMAIL'
           ORDER BY m.created_at ASC,m.id ASC""",
        (conversation_id,),
    ).fetchall()
    attachments = _client_attachments_for_messages(db, [row["id"] for row in rows])
    mark_client_notifications_read(entity_type="conversation", entity_id=conversation_id)
    messages = []
    for row in rows:
        files = []
        for item in attachments.get(int(row["id"]), []):
            files.append({
                "name": item["original_name"],
                "size_bytes": int(item["size_bytes"] or 0),
                "url": url_for("main.client_attachment", attachment_id=item["id"]),
            })
        messages.append({
            "id": int(row["id"]),
            "direction": row["direction"],
            "subject": row["subject"] or "",
            "body": row["body"] or "",
            "at": row["created_at"] or "",
            "delivery_status": row["delivery_status"] or "",
            "sender_name": row["sent_by_name"] or "",
            "attachments": files,
        })

    default_subject = (conv["subject"] or "RSF outreach").removeprefix("Re: ").strip()
    from .client_ops import email_send_configured
    return jsonify({
        "ok": True,
        "conversation_id": conversation_id,
        "recipient": conv["client_email"],
        "client_name": conv["client_name"],
        "subject": default_subject,
        "messages": messages,
        "send_url": url_for("main.communication_email_send"),
        "send_ready": email_send_configured(),
    })


@bp.post("/communications/email-send")
@login_required
def communication_email_send():
    validate_csrf()
    conversation_id = request.form.get("conversation_id", type=int)
    if not conversation_id:
        return jsonify({"ok": False, "message": "Email conversation is missing."}), 400
    _authorized_client_conversation(conversation_id)
    body = (request.form.get("body", "") or "").strip()
    subject = (request.form.get("subject", "") or "").strip()[:240]
    from .client_ops import send_client_email
    try:
        message_id = send_client_email(
            conversation_id,
            g.user["id"],
            body,
            attachments=None,
            subject_override=subject or None,
        )
    except (ValueError, RuntimeError) as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Inline client email send failed")
        return jsonify({"ok": False, "message": "RSF could not send that email. Check the email setup and try again."}), 500
    return jsonify({"ok": True, "message_id": message_id, "message": "Email sent."})


def _whatsapp_context(*, prospect_id: int | None = None, inquiry_id: int | None = None, deal_id: int | None = None):
    """Resolve the canonical Deal-owned WhatsApp # without depending on email."""
    db = get_db()
    prospect_id, inquiry_id, deal_id = _communication_context_ids(
        prospect_id=prospect_id, inquiry_id=inquiry_id, deal_id=deal_id
    )
    deal = None
    if deal_id:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id,whatsapp_number FROM deals WHERE id=?",
            (deal_id,),
        ).fetchone()
    elif prospect_id:
        deal = db.execute(
            """SELECT id,prospect_id,website_inquiry_id,whatsapp_number
               FROM deals WHERE prospect_id=? ORDER BY id DESC LIMIT 1""",
            (prospect_id,),
        ).fetchone()
    elif inquiry_id:
        deal = db.execute(
            """SELECT id,prospect_id,website_inquiry_id,whatsapp_number
               FROM deals WHERE website_inquiry_id=? ORDER BY id DESC LIMIT 1""",
            (inquiry_id,),
        ).fetchone()

    if deal:
        deal_id = int(deal["id"])
        prospect_id = int(deal["prospect_id"]) if deal["prospect_id"] is not None else prospect_id
        inquiry_id = int(deal["website_inquiry_id"]) if deal["website_inquiry_id"] is not None else inquiry_id
    return prospect_id, inquiry_id, deal_id, deal


def _whatsapp_context_where(prospect_id: int | None, inquiry_id: int | None, deal_id: int | None):
    conditions = []
    params: list[int] = []
    if prospect_id:
        conditions.append("prospect_id=?")
        params.append(prospect_id)
    if inquiry_id:
        conditions.append("website_inquiry_id=?")
        params.append(inquiry_id)
    if deal_id:
        conditions.append("deal_id=?")
        params.append(deal_id)
    return conditions, params


def _whatsapp_message_payload(row) -> dict:
    has_media = bool(row["media_bytes"])
    return {
        "id": int(row["id"]),
        "direction": row["direction"],
        "type": row["message_type"] or "text",
        "body": row["body"] or "",
        "at": row["created_at"] or "",
        "delivery_status": row["delivery_status"] or "",
        "delivery_error": row["delivery_error"] or "",
        "media_name": row["media_name"] or "",
        "media_mime_type": row["media_mime_type"] or "",
        "media_size_bytes": int(row["media_size_bytes"] or 0),
        "media_url": url_for("main.communication_whatsapp_media", message_id=row["id"]) if has_media else "",
    }


@bp.get("/communications/whatsapp-thread")
@login_required
def communication_whatsapp_thread():
    prospect_id, inquiry_id, deal_id, deal = _whatsapp_context(
        prospect_id=request.args.get("prospect_id", type=int),
        inquiry_id=request.args.get("inquiry_id", type=int),
        deal_id=request.args.get("deal_id", type=int),
    )
    number = (deal["whatsapp_number"] or "").strip() if deal else ""
    if not number:
        return jsonify({"ok": False, "message": "Add WhatsApp # first."}), 400

    from .whatsapp_ops import normalize_whatsapp_number, whatsapp_messaging_configured
    normalized = normalize_whatsapp_number(number)
    conditions, params = _whatsapp_context_where(prospect_id, inquiry_id, deal_id)
    rows = []
    if conditions:
        rows = get_db().execute(
            f"""SELECT * FROM whatsapp_messages
                WHERE {" OR ".join(conditions)}
                ORDER BY created_at ASC,id ASC""",
            params,
        ).fetchall()

    configured = whatsapp_messaging_configured()
    send_ready = bool(configured and normalized)
    if not normalized:
        connection_message = "Use an international WhatsApp number, for example +63..."
    elif not configured:
        connection_message = "RSF WhatsApp API is not connected yet."
    else:
        connection_message = ""

    return jsonify({
        "ok": True,
        "recipient": number,
        "normalized_recipient": normalized,
        "prospect_id": prospect_id,
        "inquiry_id": inquiry_id,
        "deal_id": deal_id,
        "messages": [_whatsapp_message_payload(row) for row in rows],
        "send_url": url_for("main.communication_whatsapp_send"),
        "send_ready": send_ready,
        "api_configured": configured,
        "connection_message": connection_message,
        # WhatsApp Calling is a separate capability. The UI is intentionally
        # present but stays disabled until that API is explicitly configured.
        "call_ready": False,
        "call_url": "",
        "call_status": "WhatsApp Calling is not connected yet.",
    })


def _whatsapp_media_kind(mime_type: str) -> str:
    mime = (mime_type or "").lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "document"


def _insert_whatsapp_message(
    db,
    *,
    prospect_id: int | None,
    inquiry_id: int | None,
    deal_id: int | None,
    direction: str,
    message_type: str,
    body: str,
    sender_phone: str,
    recipient_phone: str,
    external_message_id: str = "",
    delivery_status: str = "",
    delivery_error: str = "",
    media_id: str = "",
    media_name: str = "",
    media_mime_type: str = "",
    media_bytes: bytes | None = None,
    created_at: str | None = None,
) -> int:
    now = created_at or utcnow_iso()
    media_data = media_bytes if media_bytes else None
    cur = db.execute(
        """INSERT INTO whatsapp_messages(
               prospect_id,website_inquiry_id,deal_id,direction,message_type,body,
               sender_phone,recipient_phone,external_message_id,delivery_status,delivery_error,
               media_id,media_name,media_mime_type,media_size_bytes,media_bytes,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            prospect_id, inquiry_id, deal_id, direction, message_type, body,
            sender_phone, recipient_phone, external_message_id, delivery_status, delivery_error,
            media_id, media_name, media_mime_type, len(media_data or b""), media_data, now, now,
        ),
    )
    return int(cur.lastrowid)


@bp.post("/communications/whatsapp-send")
@login_required
def communication_whatsapp_send():
    validate_csrf()
    prospect_id, inquiry_id, deal_id, deal = _whatsapp_context(
        prospect_id=request.form.get("prospect_id", type=int),
        inquiry_id=request.form.get("inquiry_id", type=int),
        deal_id=request.form.get("deal_id", type=int),
    )
    number = (deal["whatsapp_number"] or "").strip() if deal else ""
    if not number:
        return jsonify({"ok": False, "message": "Add WhatsApp # first."}), 400

    from .whatsapp_ops import (
        message_id_from_response,
        normalize_whatsapp_number,
        send_media,
        send_text,
        upload_media,
        whatsapp_messaging_configured,
    )
    normalized = normalize_whatsapp_number(number)
    if not normalized:
        return jsonify({"ok": False, "message": "WhatsApp # must use a valid international number."}), 400
    if not whatsapp_messaging_configured():
        return jsonify({"ok": False, "message": "RSF WhatsApp API is not connected yet."}), 400

    body = (request.form.get("body", "") or "").strip()[:4096]
    upload = request.files.get("media")
    media_data = b""
    media_name = ""
    media_mime = ""
    message_type = "text"
    if upload and upload.filename:
        media_name = secure_filename(upload.filename)[:240] or "attachment"
        media_mime = (upload.mimetype or "application/octet-stream").strip().lower()
        message_type = _whatsapp_media_kind(media_mime)
        if message_type == "audio" and body:
            return jsonify({"ok": False, "message": "Send audio and text as separate WhatsApp messages."}), 400
        max_bytes = int(current_app.config.get("WHATSAPP_MAX_MEDIA_MB", 16)) * 1024 * 1024
        media_data = upload.read(max_bytes + 1)
        if len(media_data) > max_bytes:
            return jsonify({
                "ok": False,
                "message": f"WhatsApp attachment is larger than {current_app.config.get('WHATSAPP_MAX_MEDIA_MB', 16)} MB.",
            }), 400

    if not body and not media_data:
        return jsonify({"ok": False, "message": "Write a WhatsApp message or attach a file first."}), 400

    db = get_db()
    media_id = ""
    external_id = ""
    try:
        if media_data:
            media_id = upload_media(media_name, media_mime, media_data)
            response = send_media(
                normalized,
                media_id,
                message_type,
                filename=media_name,
                caption=body,
            )
        else:
            response = send_text(normalized, body)
        external_id = message_id_from_response(response)
        row_id = _insert_whatsapp_message(
            db,
            prospect_id=prospect_id,
            inquiry_id=inquiry_id,
            deal_id=deal_id,
            direction="OUTBOUND",
            message_type=message_type,
            body=body,
            sender_phone="",
            recipient_phone=normalized,
            external_message_id=external_id,
            delivery_status="sent",
            media_id=media_id,
            media_name=media_name,
            media_mime_type=media_mime,
            media_bytes=media_data or None,
        )
        db.commit()
    except (ValueError, RuntimeError) as exc:
        _insert_whatsapp_message(
            db,
            prospect_id=prospect_id,
            inquiry_id=inquiry_id,
            deal_id=deal_id,
            direction="OUTBOUND",
            message_type=message_type,
            body=body,
            sender_phone="",
            recipient_phone=normalized,
            external_message_id=external_id,
            delivery_status="failed",
            delivery_error=str(exc)[:1000],
            media_id=media_id,
            media_name=media_name,
            media_mime_type=media_mime,
            media_bytes=media_data or None,
        )
        db.commit()
        return jsonify({"ok": False, "message": str(exc)}), 502
    except Exception:
        db.rollback()
        current_app.logger.exception("WhatsApp send failed")
        return jsonify({"ok": False, "message": "RSF could not send that WhatsApp message."}), 500

    return jsonify({"ok": True, "message_id": row_id, "external_message_id": external_id, "message": "WhatsApp message sent."})


@bp.get("/communications/whatsapp-media/<int:message_id>")
@login_required
def communication_whatsapp_media(message_id: int):
    row = get_db().execute(
        """SELECT id,prospect_id,website_inquiry_id,deal_id,media_name,media_mime_type,media_bytes
           FROM whatsapp_messages WHERE id=?""",
        (message_id,),
    ).fetchone()
    if not row:
        abort(404)
    _communication_context_ids(
        prospect_id=int(row["prospect_id"]) if row["prospect_id"] is not None else None,
        inquiry_id=int(row["website_inquiry_id"]) if row["website_inquiry_id"] is not None else None,
        deal_id=int(row["deal_id"]) if row["deal_id"] is not None else None,
    )
    if not row["media_bytes"]:
        abort(404)
    data = bytes(row["media_bytes"])
    return send_file(
        BytesIO(data),
        mimetype=row["media_mime_type"] or "application/octet-stream",
        download_name=row["media_name"] or f"whatsapp-{message_id}",
        as_attachment=False,
        max_age=0,
    )


@bp.get("/webhooks/whatsapp")
def whatsapp_webhook_verify():
    from .whatsapp_ops import whatsapp_webhook_verify_configured
    expected = (current_app.config.get("WHATSAPP_VERIFY_TOKEN") or "").strip()
    if not whatsapp_webhook_verify_configured():
        return "WhatsApp webhook is not configured.", 503
    if (
        request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token", "") == expected
        and request.args.get("hub.challenge")
    ):
        return request.args["hub.challenge"], 200, {"Content-Type": "text/plain"}
    return "Invalid WhatsApp webhook verification.", 403


@bp.post("/webhooks/whatsapp")
def whatsapp_webhook_receive():
    from .whatsapp_ops import (
        download_media,
        normalize_whatsapp_number,
        verify_webhook_signature,
        whatsapp_messaging_configured,
        whatsapp_webhook_signature_configured,
    )
    raw = request.get_data(cache=True)
    if not whatsapp_webhook_signature_configured():
        return "WhatsApp webhook signature is not configured.", 503
    if not verify_webhook_signature(raw, request.headers.get("X-Hub-Signature-256")):
        return "Invalid WhatsApp webhook signature.", 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return "Invalid WhatsApp webhook payload.", 400

    db = get_db()
    for entry in payload.get("entry") or []:
        for change in (entry or {}).get("changes") or []:
            value = (change or {}).get("value") or {}

            for status in value.get("statuses") or []:
                external_id = str((status or {}).get("id") or "").strip()
                state = str((status or {}).get("status") or "").strip().lower()
                if not external_id or not state:
                    continue
                errors = (status or {}).get("errors") or []
                error_text = ""
                if errors:
                    first = errors[0] or {}
                    error_text = str(first.get("title") or first.get("message") or first.get("code") or "")[:1000]
                db.execute(
                    """UPDATE whatsapp_messages
                       SET delivery_status=?,delivery_error=?,updated_at=?
                       WHERE external_message_id=?""",
                    (state, error_text, utcnow_iso(), external_id),
                )

            for message in value.get("messages") or []:
                message = message or {}
                external_id = str(message.get("id") or "").strip()
                if not external_id:
                    continue
                if db.execute(
                    "SELECT 1 FROM whatsapp_messages WHERE external_message_id=? LIMIT 1",
                    (external_id,),
                ).fetchone():
                    continue

                sender = normalize_whatsapp_number(str(message.get("from") or ""))
                if not sender:
                    continue
                matched_deal = None
                candidates = db.execute(
                    """SELECT id,prospect_id,website_inquiry_id,whatsapp_number
                       FROM deals
                       WHERE trim(COALESCE(whatsapp_number,''))<>''
                       ORDER BY updated_at DESC,id DESC"""
                ).fetchall()
                for candidate in candidates:
                    if normalize_whatsapp_number(candidate["whatsapp_number"]) == sender:
                        matched_deal = candidate
                        break
                if not matched_deal:
                    continue

                kind = str(message.get("type") or "text").strip().lower()
                if kind not in {"text", "image", "video", "audio", "document"}:
                    kind = "unknown"
                body = ""
                media_id = ""
                media_name = ""
                media_mime = ""
                media_data = None
                if kind == "text":
                    body = str((message.get("text") or {}).get("body") or "")[:4096]
                elif kind in {"image", "video", "audio", "document"}:
                    media = message.get(kind) or {}
                    media_id = str(media.get("id") or "")
                    media_mime = str(media.get("mime_type") or "")
                    media_name = secure_filename(str(media.get("filename") or ""))[:240]
                    body = str(media.get("caption") or "")[:4096]
                    if not body:
                        body = media_name or f"[{kind.title()}]"
                    if media_id and whatsapp_messaging_configured():
                        try:
                            downloaded, downloaded_mime = download_media(media_id)
                            max_bytes = int(current_app.config.get("WHATSAPP_MAX_MEDIA_MB", 16)) * 1024 * 1024
                            if len(downloaded) <= max_bytes:
                                media_data = downloaded
                                media_mime = downloaded_mime or media_mime
                        except Exception:
                            current_app.logger.exception("WhatsApp inbound media download failed")
                else:
                    body = "[Unsupported WhatsApp message]"

                raw_timestamp = str(message.get("timestamp") or "").strip()
                try:
                    created_at = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc).replace(microsecond=0).isoformat()
                except (TypeError, ValueError, OSError):
                    created_at = utcnow_iso()

                _insert_whatsapp_message(
                    db,
                    prospect_id=int(matched_deal["prospect_id"]) if matched_deal["prospect_id"] is not None else None,
                    inquiry_id=int(matched_deal["website_inquiry_id"]) if matched_deal["website_inquiry_id"] is not None else None,
                    deal_id=int(matched_deal["id"]),
                    direction="INBOUND",
                    message_type=kind,
                    body=body,
                    sender_phone=sender,
                    recipient_phone="",
                    external_message_id=external_id,
                    delivery_status="received",
                    media_id=media_id,
                    media_name=media_name,
                    media_mime_type=media_mime,
                    media_bytes=media_data,
                    created_at=created_at,
                )

    db.commit()
    return "", 200



def _manual_call_context(*, prospect_id: int | None = None, inquiry_id: int | None = None, deal_id: int | None = None):
    """Resolve the page-specific Contact Number used by the Manual Call button."""
    db = get_db()
    requested_prospect_id = prospect_id
    requested_inquiry_id = inquiry_id
    requested_deal_id = deal_id
    prospect_id, inquiry_id, deal_id = _communication_context_ids(
        prospect_id=prospect_id, inquiry_id=inquiry_id, deal_id=deal_id
    )

    prospect = None
    inquiry = None
    deal = None
    if prospect_id:
        prospect = db.execute("SELECT id,phone FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if inquiry_id:
        inquiry = _authorized_inquiry(inquiry_id)
    if deal_id:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id,contact_number FROM deals WHERE id=?",
            (deal_id,),
        ).fetchone()
    elif prospect_id:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id,contact_number FROM deals WHERE prospect_id=? ORDER BY id DESC LIMIT 1",
            (prospect_id,),
        ).fetchone()
    elif inquiry_id:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id,contact_number FROM deals WHERE website_inquiry_id=? ORDER BY id DESC LIMIT 1",
            (inquiry_id,),
        ).fetchone()

    if deal and deal_id is None:
        deal_id = int(deal["id"])

    # Exact button rule: use the Contact Number belonging to the page the user
    # opened. Do not silently substitute WhatsApp # or another communication field.
    if requested_deal_id:
        phone = (deal["contact_number"] or "").strip() if deal else ""
    elif requested_inquiry_id:
        phone = (inquiry["phone"] or "").strip() if inquiry else ""
    elif requested_prospect_id:
        phone = (prospect["phone"] or "").strip() if prospect else ""
    else:
        phone = ""
    return prospect_id, inquiry_id, deal_id, phone


def _manual_call_conditions(prospect_id: int | None, inquiry_id: int | None, deal_id: int | None):
    conditions = []
    params: list[int] = []
    if prospect_id:
        conditions.append("prospect_id=?")
        params.append(prospect_id)
    if inquiry_id:
        conditions.append("website_inquiry_id=?")
        params.append(inquiry_id)
    if deal_id:
        conditions.append("deal_id=?")
        params.append(deal_id)
    return conditions, params


def _manual_call_public_url(endpoint: str, **values) -> str:
    path = url_for(endpoint, **values)
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    return f"{base}{path}" if base else url_for(endpoint, _external=True, **values)


def _twilio_request_url() -> str:
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return request.url
    full_path = request.full_path[:-1] if request.full_path.endswith("?") else request.full_path
    return f"{base}{full_path}"


def _valid_twilio_form_webhook() -> bool:
    from .twilio_manual_call_ops import validate_form_webhook
    return validate_form_webhook(
        _twilio_request_url(),
        request.form.to_dict(flat=False),
        request.headers.get("X-Twilio-Signature"),
    )


def _manual_call_authorized_row(call_id: int):
    row = get_db().execute("SELECT * FROM manual_client_calls WHERE id=?", (call_id,)).fetchone()
    if not row:
        abort(404)
    _communication_context_ids(
        prospect_id=int(row["prospect_id"]) if row["prospect_id"] is not None else None,
        inquiry_id=int(row["website_inquiry_id"]) if row["website_inquiry_id"] is not None else None,
        deal_id=int(row["deal_id"]) if row["deal_id"] is not None else None,
    )
    return row


def _manual_call_status_payload(row) -> dict:
    terminal = (row["status"] or "").upper() in {
        "COMPLETED", "BUSY", "FAILED", "NO_ANSWER", "CANCELED", "CANCELLED"
    }
    return {
        "id": int(row["id"]),
        "status": row["status"] or "",
        "caption": row["caption"] or "",
        "duration_seconds": int(row["duration_seconds"] or row["recording_duration_seconds"] or 0),
        "recording_ready": bool(row["recording_bytes"]),
        "transcript_status": row["transcript_status"] or "",
        "terminal": terminal,
        "error": row["provider_error"] or "",
    }


@bp.get("/communications/manual-call")
@login_required
def communication_manual_call():
    prospect_id, inquiry_id, deal_id, phone = _manual_call_context(
        prospect_id=request.args.get("prospect_id", type=int),
        inquiry_id=request.args.get("inquiry_id", type=int),
        deal_id=request.args.get("deal_id", type=int),
    )
    if not phone:
        return jsonify({"ok": False, "message": "Add Contact Number first."}), 400

    from .twilio_manual_call_ops import (
        batch_transcription_configured,
        manual_call_configured,
        normalize_e164,
    )
    normalized = normalize_e164(phone)
    provider_ready = manual_call_configured()
    start_ready = bool(provider_ready and normalized)
    if not normalized:
        connection_message = "Use international Contact Number format, for example +63..."
    elif not provider_ready:
        connection_message = "RSF Manual Call service is not connected yet."
    else:
        connection_message = ""

    conditions, params = _manual_call_conditions(prospect_id, inquiry_id, deal_id)
    latest = None
    if conditions:
        latest = get_db().execute(
            f"""SELECT * FROM manual_client_calls
                WHERE {" OR ".join(conditions)}
                ORDER BY created_at DESC,id DESC LIMIT 1""",
            params,
        ).fetchone()

    return jsonify({
        "ok": True,
        "recipient": phone,
        "normalized_recipient": normalized,
        "prospect_id": prospect_id,
        "inquiry_id": inquiry_id,
        "deal_id": deal_id,
        "start_url": url_for("main.communication_manual_call_start"),
        "start_ready": start_ready,
        "provider_ready": provider_ready,
        "transcription_ready": batch_transcription_configured(),
        "connection_message": connection_message,
        "recording_notice": current_app.config.get("TWILIO_RECORDING_NOTICE") or "",
        "latest_call": _manual_call_status_payload(latest) if latest else None,
        "latest_status_url": url_for("main.communication_manual_call_status", call_id=latest["id"]) if latest else "",
    })


@bp.post("/communications/manual-call/start")
@login_required
def communication_manual_call_start():
    validate_csrf()
    prospect_id, inquiry_id, deal_id, phone = _manual_call_context(
        prospect_id=request.form.get("prospect_id", type=int),
        inquiry_id=request.form.get("inquiry_id", type=int),
        deal_id=request.form.get("deal_id", type=int),
    )
    if not phone:
        return jsonify({"ok": False, "message": "Add Contact Number first."}), 400
    if request.form.get("recording_consent") != "1":
        return jsonify({"ok": False, "message": "Confirm the call-recording consent reminder before starting."}), 400

    from .twilio_manual_call_ops import create_manual_bridge_call, manual_call_configured, normalize_e164
    normalized = normalize_e164(phone)
    if not normalized:
        return jsonify({"ok": False, "message": "Contact Number must use international format, for example +63..."}), 400
    if not manual_call_configured():
        return jsonify({"ok": False, "message": "RSF Manual Call service is not connected yet."}), 400

    db = get_db()
    open_call = db.execute(
        """SELECT id FROM manual_client_calls
           WHERE status IN ('STARTING','QUEUED','AGENT_RINGING','AGENT_CONNECTED','CLIENT_RINGING','IN_PROGRESS')
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    if open_call:
        return jsonify({"ok": False, "message": "Finish the current Manual Call first."}), 409

    now = utcnow_iso()
    webhook_token = uuid4().hex
    caption = (request.form.get("caption", "") or "").strip()[:240] or f"Manual call with {normalized}"
    cur = db.execute(
        """INSERT INTO manual_client_calls(
               prospect_id,website_inquiry_id,deal_id,initiated_by_user_id,provider,provider_call_sid,
               webhook_token,phone,status,caption,transcript,transcript_status,transcription_id,
               provider_error,recording_sid,recording_mime_type,recording_size_bytes,recording_bytes,
               recording_duration_seconds,duration_seconds,started_at,answered_at,ended_at,created_at,updated_at
           ) VALUES (?,?,?,?,'TWILIO','',?,?,'STARTING',?,'','NOT_REQUESTED','','','','',0,NULL,0,0,?,'','',?,?)""",
        (
            prospect_id, inquiry_id, deal_id, g.user["id"], webhook_token, normalized,
            caption, now, now, now,
        ),
    )
    call_id = int(cur.lastrowid)
    db.commit()

    twiml_url = _manual_call_public_url("main.twilio_manual_call_twiml", token=webhook_token)
    status_url = _manual_call_public_url("main.twilio_manual_call_status_webhook", token=webhook_token, leg="agent")
    try:
        provider_sid = create_manual_bridge_call(
            twiml_url=twiml_url,
            status_callback_url=status_url,
        )
        db.execute(
            "UPDATE manual_client_calls SET provider_call_sid=?,status='QUEUED',updated_at=? WHERE id=?",
            (provider_sid, utcnow_iso(), call_id),
        )
        db.commit()
    except (ValueError, RuntimeError) as exc:
        db.execute(
            "UPDATE manual_client_calls SET status='FAILED',provider_error=?,ended_at=?,updated_at=? WHERE id=?",
            (str(exc)[:1200], utcnow_iso(), utcnow_iso(), call_id),
        )
        db.commit()
        return jsonify({"ok": False, "message": str(exc)}), 502
    except Exception:
        db.execute(
            "UPDATE manual_client_calls SET status='FAILED',provider_error='Unexpected provider error.',ended_at=?,updated_at=? WHERE id=?",
            (utcnow_iso(), utcnow_iso(), call_id),
        )
        db.commit()
        current_app.logger.exception("Manual Call start failed")
        return jsonify({"ok": False, "message": "RSF could not start the Manual Call."}), 500

    return jsonify({
        "ok": True,
        "call_id": call_id,
        "message": "Manual Call started. Your configured caller phone will ring first.",
        "status_url": url_for("main.communication_manual_call_status", call_id=call_id),
    })


@bp.get("/communications/manual-call/<int:call_id>/status")
@login_required
def communication_manual_call_status(call_id: int):
    return jsonify({"ok": True, "call": _manual_call_status_payload(_manual_call_authorized_row(call_id))})


@bp.get("/communications/manual-call/<int:call_id>/recording")
@login_required
def communication_manual_call_recording(call_id: int):
    row = _manual_call_authorized_row(call_id)
    if not row["recording_bytes"]:
        abort(404)
    data = bytes(row["recording_bytes"])
    return send_file(
        BytesIO(data),
        mimetype=row["recording_mime_type"] or "audio/mpeg",
        download_name=f"manual-call-{call_id}.mp3",
        as_attachment=False,
        max_age=0,
    )


@bp.post("/webhooks/twilio/manual-call/<token>/twiml")
def twilio_manual_call_twiml(token: str):
    db = get_db()
    row = db.execute("SELECT * FROM manual_client_calls WHERE webhook_token=?", (token,)).fetchone()
    if not row:
        abort(404)
    if not _valid_twilio_form_webhook():
        return "Invalid Twilio signature.", 403

    from .twilio_manual_call_ops import normalize_e164
    client_phone = normalize_e164(row["phone"])
    if not client_phone:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Client number is invalid.</Say><Hangup/></Response>',
            mimetype="text/xml",
        )

    from_number = html_lib.escape(current_app.config.get("TWILIO_FROM_NUMBER") or "", quote=True)
    client_number = html_lib.escape(client_phone, quote=True)
    notice_url = html_lib.escape(
        _manual_call_public_url("main.twilio_manual_call_client_notice", token=token),
        quote=True,
    )
    client_status_url = html_lib.escape(
        _manual_call_public_url("main.twilio_manual_call_status_webhook", token=token, leg="client"),
        quote=True,
    )
    recording_url = html_lib.escape(
        _manual_call_public_url("main.twilio_manual_call_recording_webhook", token=token),
        quote=True,
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Dial callerId="{from_number}" answerOnBridge="true" record="record-from-answer-dual" '
        f'recordingStatusCallback="{recording_url}" recordingStatusCallbackMethod="POST" '
        f'recordingStatusCallbackEvent="completed absent">'
        f'<Number url="{notice_url}" method="POST" statusCallback="{client_status_url}" '
        f'statusCallbackMethod="POST" statusCallbackEvent="initiated ringing answered completed">{client_number}</Number>'
        '</Dial>'
        '</Response>'
    )
    return Response(xml, mimetype="text/xml")


@bp.post("/webhooks/twilio/manual-call/<token>/client-notice")
def twilio_manual_call_client_notice(token: str):
    row = get_db().execute("SELECT id FROM manual_client_calls WHERE webhook_token=?", (token,)).fetchone()
    if not row:
        abort(404)
    if not _valid_twilio_form_webhook():
        return "Invalid Twilio signature.", 403
    notice = html_lib.escape(
        current_app.config.get("TWILIO_RECORDING_NOTICE") or "This call may be recorded.",
        quote=False,
    )
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>{notice}</Say></Response>',
        mimetype="text/xml",
    )


@bp.post("/webhooks/twilio/manual-call/<token>/status")
def twilio_manual_call_status_webhook(token: str):
    db = get_db()
    row = db.execute("SELECT * FROM manual_client_calls WHERE webhook_token=?", (token,)).fetchone()
    if not row:
        abort(404)
    if not _valid_twilio_form_webhook():
        return "Invalid Twilio signature.", 403

    raw_status = (request.form.get("CallStatus", "") or "").strip().lower()
    leg = (request.args.get("leg", "") or "").strip().lower()
    status_map = {
        "initiated": "CLIENT_RINGING" if leg == "client" else "QUEUED",
        "queued": "QUEUED",
        "ringing": "CLIENT_RINGING" if leg == "client" else "AGENT_RINGING",
        "answered": "IN_PROGRESS" if leg == "client" else "AGENT_CONNECTED",
        "in-progress": "IN_PROGRESS" if leg == "client" else "AGENT_CONNECTED",
        "completed": "COMPLETED",
        "busy": "BUSY",
        "failed": "FAILED",
        "no-answer": "NO_ANSWER",
        "canceled": "CANCELED",
        "cancelled": "CANCELED",
    }
    mapped = status_map.get(raw_status)
    if not mapped:
        return "", 204

    now = utcnow_iso()
    updates = ["status=?", "updated_at=?"]
    params: list = [mapped, now]
    if leg == "client" and raw_status in {"answered", "in-progress"} and not row["answered_at"]:
        updates.append("answered_at=?")
        params.append(now)
    terminal = raw_status in {"completed", "busy", "failed", "no-answer", "canceled", "cancelled"}
    if terminal and (leg == "client" or not row["ended_at"]):
        updates.append("ended_at=?")
        params.append(now)
        try:
            duration = int(request.form.get("CallDuration") or 0)
        except (TypeError, ValueError):
            duration = 0
        if duration > 0:
            updates.append("duration_seconds=?")
            params.append(duration)
    error_code = (request.form.get("ErrorCode", "") or "").strip()
    if error_code:
        updates.append("provider_error=?")
        params.append(f"Twilio error {error_code}"[:1200])
    params.append(int(row["id"]))
    db.execute(f"UPDATE manual_client_calls SET {','.join(updates)} WHERE id=?", params)
    db.commit()
    return "", 204


@bp.post("/webhooks/twilio/manual-call/<token>/recording")
def twilio_manual_call_recording_webhook(token: str):
    db = get_db()
    row = db.execute("SELECT * FROM manual_client_calls WHERE webhook_token=?", (token,)).fetchone()
    if not row:
        abort(404)
    if not _valid_twilio_form_webhook():
        return "Invalid Twilio signature.", 403

    recording_status = (request.form.get("RecordingStatus", "") or "").strip().lower()
    recording_sid = (request.form.get("RecordingSid", "") or "").strip()
    recording_url = (request.form.get("RecordingUrl", "") or "").strip()
    try:
        recording_duration = int(request.form.get("RecordingDuration") or 0)
    except (TypeError, ValueError):
        recording_duration = 0
    now = utcnow_iso()

    if recording_status != "completed" or not recording_sid or not recording_url:
        db.execute(
            """UPDATE manual_client_calls
               SET provider_error=?,recording_duration_seconds=?,updated_at=?
               WHERE id=?""",
            ("Recording was not available.", recording_duration, now, row["id"]),
        )
        db.commit()
        return "", 204

    from .twilio_manual_call_ops import (
        batch_transcription_configured,
        create_batch_transcription,
        download_recording,
    )
    try:
        recording_bytes, mime_type = download_recording(recording_url)
        max_bytes = int(current_app.config.get("TWILIO_RECORDING_MAX_MB", 32)) * 1024 * 1024
        if len(recording_bytes) > max_bytes:
            raise RuntimeError(
                f"Manual Call recording exceeds the protected RSF limit of {current_app.config.get('TWILIO_RECORDING_MAX_MB', 32)} MB."
            )
        db.execute(
            """UPDATE manual_client_calls
               SET recording_sid=?,recording_mime_type=?,recording_size_bytes=?,recording_bytes=?,
                   recording_duration_seconds=?,duration_seconds=CASE WHEN duration_seconds=0 THEN ? ELSE duration_seconds END,
                   updated_at=?
               WHERE id=?""",
            (
                recording_sid, mime_type, len(recording_bytes), recording_bytes,
                recording_duration, recording_duration, now, row["id"],
            ),
        )
        db.commit()
    except Exception as exc:
        db.execute(
            "UPDATE manual_client_calls SET provider_error=?,updated_at=? WHERE id=?",
            (f"Recording save failed: {str(exc)}"[:1200], now, row["id"]),
        )
        db.commit()
        current_app.logger.exception("Manual Call recording save failed")
        return "", 204

    if batch_transcription_configured():
        try:
            transcription_id = create_batch_transcription(recording_sid)
            db.execute(
                """UPDATE manual_client_calls
                   SET transcription_id=?,transcript_status='PENDING',updated_at=?
                   WHERE id=?""",
                (transcription_id, utcnow_iso(), row["id"]),
            )
            db.commit()
        except Exception as exc:
            db.execute(
                """UPDATE manual_client_calls
                   SET transcript_status='FAILED',provider_error=?,updated_at=?
                   WHERE id=?""",
                (f"Transcription start failed: {str(exc)}"[:1200], utcnow_iso(), row["id"]),
            )
            db.commit()
            current_app.logger.exception("Manual Call transcription start failed")
    return "", 204


@bp.post("/webhooks/twilio/manual-call/transcription/<secret>")
def twilio_manual_call_transcription_webhook(secret: str):
    expected = (current_app.config.get("TWILIO_TRANSCRIPTION_WEBHOOK_SECRET") or "").strip()
    if not expected or not __import__("hmac").compare_digest(expected, secret):
        return "Invalid transcription webhook secret.", 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return "Invalid transcription payload.", 400
    account_id = str(payload.get("accountId") or "").strip()
    expected_account = (current_app.config.get("TWILIO_ACCOUNT_SID") or "").strip()
    if expected_account and account_id != expected_account:
        return "Invalid transcription account.", 403

    recording_sid = str(payload.get("sourceId") or "").strip()
    if not recording_sid:
        return "", 204
    db = get_db()
    row = db.execute("SELECT * FROM manual_client_calls WHERE recording_sid=?", (recording_sid,)).fetchone()
    if not row:
        return "", 204

    status = str(payload.get("status") or "").strip().lower()
    if status != "completed":
        error = payload.get("error") or {}
        message = str(error.get("message") or "Transcription failed.")[:1200]
        db.execute(
            """UPDATE manual_client_calls
               SET transcript_status='FAILED',provider_error=?,updated_at=?
               WHERE id=?""",
            (message, utcnow_iso(), row["id"]),
        )
        db.commit()
        return "", 204

    participants = payload.get("participants") or []
    labels = {}
    for index, participant in enumerate(participants):
        participant = participant or {}
        ptype = str(participant.get("type") or "").upper()
        if ptype == "CUSTOMER":
            label = "Client"
        elif ptype == "HUMAN_AGENT":
            label = "You"
        else:
            label = str(participant.get("name") or f"Speaker {index + 1}")
        labels[index] = label

    transcript_lines = []
    for sentence in payload.get("sentences") or []:
        sentence = sentence or {}
        text_value = str(sentence.get("text") or "").strip()
        if not text_value:
            continue
        try:
            start_seconds = max(0, int(float(sentence.get("startTimeSeconds") or 0)))
        except (TypeError, ValueError):
            start_seconds = 0
        participant_index = sentence.get("participantIndex")
        if isinstance(participant_index, int) and participant_index in labels:
            speaker = labels[participant_index]
        else:
            speaker = "You" if int(sentence.get("audioChannelIndex") or 1) == 1 else "Client"
        minutes, seconds = divmod(start_seconds, 60)
        transcript_lines.append(f"[{minutes:02d}:{seconds:02d}] {speaker}: {text_value}")

    transcript = "\n".join(transcript_lines).strip()
    db.execute(
        """UPDATE manual_client_calls
           SET transcript=?,transcript_status='COMPLETED',updated_at=?
           WHERE id=?""",
        (transcript, utcnow_iso(), row["id"]),
    )
    db.commit()
    return "", 204



def _retell_e164(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if not raw.startswith("+"):
        return ""
    digits = "".join(ch for ch in raw[1:] if ch.isdigit())
    return f"+{digits}" if 8 <= len(digits) <= 15 else ""


def _retell_timestamp(value) -> str:
    try:
        stamp = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if stamp <= 0:
        return ""
    # Retell timestamps are milliseconds in call payloads.
    return datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).replace(microsecond=0).isoformat()


def _retell_result_code(call: dict) -> tuple[str, str]:
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}
    raw = (
        custom.get("call_result")
        or custom.get("result")
        or custom.get("sales_result")
        or ""
    )
    normalized = str(raw).strip().upper().replace(" ", "_").replace("-", "_")
    next_step = str(custom.get("next_step") or "").strip()
    if "REJECT" in normalized or normalized in {"NOT_INTERESTED", "DECLINED"}:
        return "REJECTED", next_step
    if "DEMO" in normalized:
        return "DEMO", next_step
    if normalized in {"INTERESTED", "DEAL", "QUALIFIED", "WANTS_DEMO"}:
        return "DEAL", next_step
    if normalized in {"NO_ANSWER", "BUSY", "VOICEMAIL"}:
        return "NO_ANSWER", next_step

    reason = str(call.get("disconnection_reason") or "").strip().lower()
    if reason in {"dial_no_answer", "dial_busy", "user_declined", "voicemail_reached"}:
        return "NO_ANSWER", next_step
    if reason in {"dial_failed", "invalid_destination"}:
        return "CALL_FAILED", next_step
    return (normalized or "COMPLETED"), next_step


def _apply_ai_sales_result(db, ai_call, result: str, next_step: str, now: str) -> int | None:
    prospect_id = int(ai_call["prospect_id"])
    prospect = db.execute("SELECT status FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    if not prospect:
        return None
    current = (prospect["status"] or "").upper()
    if current in DEAL_ACTIVE_STATUSES:
        deal = db.execute("SELECT id FROM deals WHERE prospect_id=? LIMIT 1", (prospect_id,)).fetchone()
        return int(deal["id"]) if deal else None

    if result == "NO_ANSWER":
        db.execute("UPDATE prospects SET status='NO_ANSWER',updated_at=? WHERE id=?", (now, prospect_id))
        return None
    if result == "REJECTED":
        db.execute("UPDATE prospects SET status='REJECTED',updated_at=? WHERE id=?", (now, prospect_id))
        return None
    if result in {"DEAL", "DEMO"}:
        founder = db.execute(
            "SELECT id FROM users WHERE role='admin' AND active=1 ORDER BY id LIMIT 1"
        ).fetchone()
        actor_id = int(founder["id"]) if founder else None
        deal_id, _created = _ensure_deal_for_prospect(db, prospect_id, actor_id, now)
        status = result
        db.execute(
            "UPDATE deals SET status=?,next_step=CASE WHEN ?<>'' THEN ? ELSE next_step END,updated_at=? WHERE id=?",
            (status, next_step, next_step[:500], now, deal_id),
        )
        _sync_deal_source_statuses(db, deal_id, status, now)
        return deal_id
    return None


@bp.post("/prospects/<int:prospect_id>/ai-call")
@login_required
def prospect_ai_call(prospect_id: int):
    validate_csrf()
    db = get_db()
    prospect = db.execute(
        """SELECT id,name,contact,email,phone,business_type,problem,platform_wanted,
                  system_wanted,budget,location,website,status,contact_attempt
           FROM prospects WHERE id=?""",
        (prospect_id,),
    ).fetchone()
    if not prospect:
        abort(404)
    if (prospect["status"] or "").upper() in DEAL_ACTIVE_STATUSES:
        return jsonify({"ok": False, "message": "AI Call stops once the Prospect enters Deals."}), 409

    api_key = current_app.config.get("RETELL_API_KEY", "")
    agent_id = current_app.config.get("RETELL_AGENT_ID", "")
    from_number = _retell_e164(current_app.config.get("RETELL_FROM_NUMBER", ""))
    to_number = _retell_e164(prospect["phone"] or "")
    if not api_key or not agent_id or not from_number:
        return jsonify({"ok": False, "message": "Retell AI is not configured yet. Add the API key, sales agent ID, and Retell phone number."}), 503
    if not to_number:
        return jsonify({"ok": False, "message": "Prospect phone must use international E.164 format, for example +15551234567."}), 400

    attempt = int(db.execute(
        "SELECT COALESCE(MAX(attempt_number),0)+1 n FROM ai_sales_calls WHERE prospect_id=?",
        (prospect_id,),
    ).fetchone()["n"])
    now = utcnow_iso()
    cur = db.execute(
        """INSERT INTO ai_sales_calls(
               prospect_id,attempt_number,status,phone,created_at,updated_at
           ) VALUES (?,?,?,?,?,?)""",
        (prospect_id, attempt, "STARTING", to_number, now, now),
    )
    ai_call_id = int(cur.lastrowid)
    db.commit()

    variables = {
        "client_name": str(prospect["contact"] or prospect["name"] or ""),
        "company": str(prospect["name"] or ""),
        "business_type": str(prospect["business_type"] or ""),
        "problem": str(prospect["problem"] or ""),
        "system_wanted": str(prospect["system_wanted"] or ""),
        "platform_wanted": str(prospect["platform_wanted"] or ""),
        "budget": str(prospect["budget"] or ""),
        "location": str(prospect["location"] or ""),
        "website": str(prospect["website"] or ""),
        "email": str(prospect["email"] or ""),
    }
    metadata = {
        "rsf_ai_call_id": ai_call_id,
        "rsf_prospect_id": prospect_id,
        "rsf_source": "researched_prospect",
    }
    try:
        from retell import Retell
        client = Retell(api_key=api_key)
        response = client.call.create_phone_call(
            from_number=from_number,
            to_number=to_number,
            override_agent_id=agent_id,
            metadata=metadata,
            retell_llm_dynamic_variables=variables,
        )
        call_id = getattr(response, "call_id", "") or ""
        if not call_id and hasattr(response, "model_dump"):
            call_id = str(response.model_dump().get("call_id") or "")
        if not call_id:
            raise RuntimeError("Retell did not return a call ID.")
    except Exception as exc:
        current_app.logger.exception("Retell AI outbound call failed")
        db.execute(
            "UPDATE ai_sales_calls SET status='FAILED',result='CALL_FAILED',updated_at=? WHERE id=?",
            (utcnow_iso(), ai_call_id),
        )
        db.commit()
        return jsonify({"ok": False, "message": f"Retell could not start the call: {str(exc)[:240]}"}), 502

    now = utcnow_iso()
    db.execute(
        """UPDATE ai_sales_calls
           SET retell_call_id=?,status='INITIATED',updated_at=?
           WHERE id=?""",
        (call_id, now, ai_call_id),
    )
    db.execute(
        "UPDATE prospects SET contact_attempt=contact_attempt+1,updated_at=? WHERE id=?",
        (now, prospect_id),
    )
    db.commit()
    return jsonify({
        "ok": True,
        "message": "AI sales call started.",
        "call_id": call_id,
        "ai_call_id": ai_call_id,
        "attempt_number": attempt,
    })


@bp.post("/integrations/retell/webhook")
def retell_webhook():
    api_key = current_app.config.get("RETELL_API_KEY", "")
    signature = request.headers.get("X-Retell-Signature", "")
    raw = request.get_data(as_text=True)
    if not api_key or not signature:
        return "", 401
    try:
        from retell import Retell
        if not Retell.verify(raw, api_key, signature):
            return "", 401
    except Exception:
        current_app.logger.exception("Retell webhook verification failed")
        return "", 401

    payload = request.get_json(silent=True) or {}
    event = str(payload.get("event") or "")
    call = payload.get("call") or {}
    call_id = str(call.get("call_id") or "")
    metadata = call.get("metadata") or {}
    ai_call_id = metadata.get("rsf_ai_call_id")
    db = get_db()
    ai_call = None
    if call_id:
        ai_call = db.execute("SELECT * FROM ai_sales_calls WHERE retell_call_id=?", (call_id,)).fetchone()
    if not ai_call and ai_call_id:
        ai_call = db.execute("SELECT * FROM ai_sales_calls WHERE id=?", (int(ai_call_id),)).fetchone()
    if not ai_call:
        return "", 204

    now = utcnow_iso()
    started_at = _retell_timestamp(call.get("start_timestamp"))
    ended_at = _retell_timestamp(call.get("end_timestamp"))
    duration = 0
    try:
        start_ms = int(call.get("start_timestamp") or 0)
        end_ms = int(call.get("end_timestamp") or 0)
        if end_ms > start_ms > 0:
            duration = max(0, int((end_ms - start_ms) / 1000))
    except (TypeError, ValueError):
        duration = 0

    if event == "call_started":
        db.execute(
            """UPDATE ai_sales_calls SET status='IN_PROGRESS',
               started_at=CASE WHEN ?<>'' THEN ? ELSE started_at END,updated_at=?
               WHERE id=?""",
            (started_at, started_at, now, ai_call["id"]),
        )
    elif event in {"call_ended", "call_analyzed"}:
        result, next_step = _retell_result_code(call)
        analysis = call.get("call_analysis") or {}
        summary = str(analysis.get("call_summary") or analysis.get("summary") or "")
        transcript = str(call.get("transcript") or "")
        recording_url = str(call.get("recording_url") or "")
        deal_id = _apply_ai_sales_result(db, ai_call, result, next_step, now)
        db.execute(
            """UPDATE ai_sales_calls
               SET retell_call_id=COALESCE(NULLIF(?,''),retell_call_id),
                   deal_id=COALESCE(?,deal_id),status=?,result=?,
                   duration_seconds=CASE WHEN ?>0 THEN ? ELSE duration_seconds END,
                   recording_url=CASE WHEN ?<>'' THEN ? ELSE recording_url END,
                   transcript=CASE WHEN ?<>'' THEN ? ELSE transcript END,
                   summary=CASE WHEN ?<>'' THEN ? ELSE summary END,
                   next_step=CASE WHEN ?<>'' THEN ? ELSE next_step END,
                   disconnection_reason=?,
                   started_at=CASE WHEN ?<>'' THEN ? ELSE started_at END,
                   ended_at=CASE WHEN ?<>'' THEN ? ELSE ended_at END,
                   updated_at=?
               WHERE id=?""",
            (
                call_id, deal_id,
                "ANALYZED" if event == "call_analyzed" else "ENDED",
                result,
                duration, duration,
                recording_url, recording_url,
                transcript, transcript,
                summary, summary,
                next_step, next_step,
                str(call.get("disconnection_reason") or ""),
                started_at, started_at,
                ended_at, ended_at,
                now,
                ai_call["id"],
            ),
        )
    db.commit()
    return "", 204


@bp.get("/communications/timeline")
@login_required
def communication_timeline():
    db = get_db()
    prospect_id = request.args.get("prospect_id", type=int)
    inquiry_id = request.args.get("inquiry_id", type=int)
    deal_id = request.args.get("deal_id", type=int)

    deal = None
    if deal_id:
        deal = db.execute(
            "SELECT id,prospect_id,website_inquiry_id,contact_number,whatsapp_number,email,notes_after_conversation,updated_at FROM deals WHERE id=?",
            (deal_id,),
        ).fetchone()
        if not deal:
            abort(404)
        prospect_id = int(deal["prospect_id"]) if deal["prospect_id"] is not None else prospect_id
        inquiry_id = int(deal["website_inquiry_id"]) if deal["website_inquiry_id"] is not None else inquiry_id

    inquiry = _authorized_inquiry(inquiry_id) if inquiry_id else None
    prospect = None
    if prospect_id:
        prospect = db.execute(
            "SELECT id,name,contact,email,phone,notes_after_conversation,updated_at,recorded_date,status FROM prospects WHERE id=?",
            (prospect_id,),
        ).fetchone()
        if not prospect:
            abort(404)

    if not deal and not inquiry and not prospect:
        abort(400)

    # WhatsApp # is canonical on the Deal workspace even while a source is still
    # pre-Deal, so resolve that provisional/shared row without changing note behavior.
    whatsapp_deal = deal
    if not whatsapp_deal and prospect_id:
        whatsapp_deal = db.execute(
            """SELECT id,prospect_id,website_inquiry_id,whatsapp_number
               FROM deals WHERE prospect_id=? ORDER BY id DESC LIMIT 1""",
            (prospect_id,),
        ).fetchone()
    if not whatsapp_deal and inquiry_id:
        whatsapp_deal = db.execute(
            """SELECT id,prospect_id,website_inquiry_id,whatsapp_number
               FROM deals WHERE website_inquiry_id=? ORDER BY id DESC LIMIT 1""",
            (inquiry_id,),
        ).fetchone()
    whatsapp_deal_id = int(whatsapp_deal["id"]) if whatsapp_deal else None

    conversation_ids: set[int] = set()
    if inquiry:
        if inquiry["client_conversation_id"]:
            conversation_ids.add(int(inquiry["client_conversation_id"]))
        rows = db.execute(
            "SELECT id FROM client_conversations WHERE inquiry_id=?",
            (inquiry_id,),
        ).fetchall()
        conversation_ids.update(int(row["id"]) for row in rows)
    if prospect:
        rows = db.execute(
            "SELECT id FROM client_conversations WHERE prospect_id=?",
            (prospect_id,),
        ).fetchall()
        conversation_ids.update(int(row["id"]) for row in rows)

    entries: list[dict] = []
    if conversation_ids:
        placeholders = ",".join("?" for _ in conversation_ids)
        messages = db.execute(
            f"""SELECT m.*,c.inquiry_id,c.prospect_id
                FROM client_messages m
                JOIN client_conversations c ON c.id=m.conversation_id
                WHERE m.conversation_id IN ({placeholders})
                ORDER BY m.created_at ASC,m.id ASC""",
            sorted(conversation_ids),
        ).fetchall()
        for message in messages:
            source = (message["journey_source"] or "").strip().upper()
            if source not in ("OUTBOUND", "INBOUND"):
                source = "INBOUND" if message["inquiry_id"] is not None or message["channel"] == "WEBSITE" else "OUTBOUND"
            channel = "WEBSITE MESSAGE" if message["channel"] == "WEBSITE" else (message["channel"] or "NOTE").upper()
            entries.append({
                "id": f"message-{message['id']}",
                "at": message["created_at"] or "",
                "source": source,
                "channel": channel,
                "direction": "CLIENT" if message["direction"] == "INBOUND" else "RSF",
                "body": message["body"] or "",
            })

    whatsapp_conditions = []
    whatsapp_params: list[int] = []
    if prospect_id:
        whatsapp_conditions.append("prospect_id=?")
        whatsapp_params.append(prospect_id)
    if inquiry_id:
        whatsapp_conditions.append("website_inquiry_id=?")
        whatsapp_params.append(inquiry_id)
    if whatsapp_deal_id:
        whatsapp_conditions.append("deal_id=?")
        whatsapp_params.append(whatsapp_deal_id)
    if whatsapp_conditions:
        whatsapp_rows = db.execute(
            f"""SELECT id,direction,message_type,body,media_name,created_at
                FROM whatsapp_messages
                WHERE {" OR ".join(whatsapp_conditions)}
                ORDER BY created_at ASC,id ASC""",
            whatsapp_params,
        ).fetchall()
        for message in whatsapp_rows:
            display_body = (message["body"] or "").strip()
            if not display_body:
                display_body = (message["media_name"] or "").strip() or f"[{(message['message_type'] or 'message').title()}]"
            entries.append({
                "id": f"whatsapp-{message['id']}",
                "at": message["created_at"] or "",
                "source": "INBOUND" if message["direction"] == "INBOUND" else "OUTBOUND",
                "channel": "WHATSAPP",
                "direction": "CLIENT" if message["direction"] == "INBOUND" else "RSF",
                "body": display_body,
            })

    manual_call_conditions, manual_call_params = _manual_call_conditions(prospect_id, inquiry_id, whatsapp_deal_id or deal_id)
    if manual_call_conditions:
        manual_rows = db.execute(
            f"""SELECT * FROM manual_client_calls
                WHERE {" OR ".join(manual_call_conditions)}
                ORDER BY created_at ASC,id ASC""",
            manual_call_params,
        ).fetchall()
        for manual_call in manual_rows:
            duration = int(manual_call["duration_seconds"] or manual_call["recording_duration_seconds"] or 0)
            entries.append({
                "id": f"manual-call-{manual_call['id']}",
                "at": manual_call["started_at"] or manual_call["created_at"] or "",
                "source": "INBOUND" if inquiry_id else "OUTBOUND",
                "channel": "MANUAL CALL",
                "direction": "RSF",
                "body": manual_call["caption"] or "Manual call",
                "caption": manual_call["caption"] or "Manual call",
                "status": manual_call["status"] or "",
                "duration_seconds": duration,
                "recording_url": url_for("main.communication_manual_call_recording", call_id=manual_call["id"]) if manual_call["recording_bytes"] else "",
                "transcript": manual_call["transcript"] or "",
                "transcript_status": manual_call["transcript_status"] or "",
            })

    note_conditions = []
    note_params: list[int] = []
    if prospect_id:
        note_conditions.append("prospect_id=?")
        note_params.append(prospect_id)
    if inquiry_id:
        note_conditions.append("website_inquiry_id=?")
        note_params.append(inquiry_id)
    if deal_id:
        note_conditions.append("deal_id=?")
        note_params.append(deal_id)
    if note_conditions:
        note_rows = db.execute(
            f"""SELECT id,journey_source,body,created_at
                FROM communication_notes
                WHERE {" OR ".join(note_conditions)}
                ORDER BY created_at ASC,id ASC""",
            note_params,
        ).fetchall()
        for note in note_rows:
            entries.append({
                "id": f"manual-note-{note['id']}",
                "at": note["created_at"] or "",
                "source": (note["journey_source"] or "OUTBOUND").strip().upper(),
                "channel": "NOTE",
                "direction": "RSF",
                "body": note["body"] or "",
                "editable": True,
                "note_kind": "manual",
                "note_id": int(note["id"]),
            })

    seen_notes: set[str] = set()
    if prospect and (prospect["notes_after_conversation"] or "").strip():
        body = (prospect["notes_after_conversation"] or "").strip()
        seen_notes.add(body)
        entries.append({
            "id": f"prospect-note-{prospect_id}",
            "at": prospect["updated_at"] or prospect["recorded_date"] or "",
            "source": "OUTBOUND",
            "channel": "NOTE",
            "direction": "RSF",
            "body": body,
            "editable": True,
            "note_kind": "legacy",
            "source_type": "prospect",
            "source_id": int(prospect_id),
        })

    if inquiry:
        website_body = (inquiry["message"] or "").strip()
        already_has_website_message = any(
            item["channel"] == "WEBSITE MESSAGE" and item["body"].strip() == website_body
            for item in entries
        )
        if website_body and not already_has_website_message:
            entries.append({
                "id": f"inquiry-message-{inquiry_id}",
                "at": inquiry["created_at"] or "",
                "source": "INBOUND",
                "channel": "WEBSITE MESSAGE",
                "direction": "CLIENT",
                "body": website_body,
            })

        note_body = (inquiry["notes_after_conversation"] or "").strip()
        if note_body and note_body not in seen_notes:
            seen_notes.add(note_body)
            entries.append({
                "id": f"inquiry-note-{inquiry_id}",
                "at": inquiry["updated_at"] or inquiry["created_at"] or "",
                "source": "INBOUND",
                "channel": "NOTE",
                "direction": "RSF",
                "body": note_body,
                "editable": True,
                "note_kind": "legacy",
                "source_type": "inquiry",
                "source_id": int(inquiry_id),
            })

    if deal:
        note_body = (deal["notes_after_conversation"] or "").strip()
        if note_body and note_body not in seen_notes:
            entries.append({
                "id": f"deal-note-{deal_id}",
                "at": deal["updated_at"] or "",
                "source": "INBOUND" if inquiry_id else "OUTBOUND",
                "channel": "NOTE",
                "direction": "RSF",
                "body": note_body,
                "editable": True,
                "note_kind": "legacy",
                "source_type": "deal",
                "source_id": int(deal_id),
            })

    if prospect_id:
        ai_rows = db.execute(
            """SELECT * FROM ai_sales_calls
               WHERE prospect_id=?
               ORDER BY created_at ASC,id ASC""",
            (prospect_id,),
        ).fetchall()
        for call in ai_rows:
            entries.append({
                "id": f"ai-sales-call-{call['id']}",
                "at": call["created_at"] or "",
                "source": "OUTBOUND",
                "channel": "AI SALES CALL",
                "direction": "RSF",
                "body": call["summary"] or call["result"] or call["status"] or "AI sales call",
                "attempt_number": int(call["attempt_number"] or 1),
                "duration_seconds": int(call["duration_seconds"] or 0),
                "result": call["result"] or call["status"] or "",
                "recording_url": call["recording_url"] or "",
                "transcript": call["transcript"] or "",
                "summary": call["summary"] or "",
                "next_step": call["next_step"] or "",
            })

    entries.sort(key=lambda item: (item["at"], item["id"]))

    phone = ""
    email = ""
    if inquiry:
        phone = (inquiry["phone"] or "").strip()
        email = (inquiry["email"] or "").strip()
    if prospect:
        phone = phone or (prospect["phone"] or "").strip()
        email = email or (prospect["email"] or "").strip()
    if deal:
        phone = phone or (deal["contact_number"] or "").strip()
        email = email or (deal["email"] or "").strip()

    whatsapp_number = (whatsapp_deal["whatsapp_number"] or "").strip() if whatsapp_deal else ""

    preferred_conversation_id = None
    if inquiry and inquiry["client_conversation_id"]:
        preferred_conversation_id = int(inquiry["client_conversation_id"])
    elif conversation_ids:
        preferred_conversation_id = max(conversation_ids)

    email_url = ""
    if email:
        if deal_id:
            email_url = url_for("main.communication_email_thread", deal_id=deal_id)
        elif inquiry_id:
            email_url = url_for("main.communication_email_thread", inquiry_id=inquiry_id)
        elif prospect_id:
            email_url = url_for("main.communication_email_thread", prospect_id=prospect_id)

    whatsapp_url = ""
    if whatsapp_number:
        if deal_id:
            whatsapp_url = url_for("main.communication_whatsapp_thread", deal_id=deal_id)
        elif inquiry_id:
            whatsapp_url = url_for("main.communication_whatsapp_thread", inquiry_id=inquiry_id)
        elif prospect_id:
            whatsapp_url = url_for("main.communication_whatsapp_thread", prospect_id=prospect_id)

    manual_call_url = ""
    requested_deal_id = request.args.get("deal_id", type=int)
    requested_inquiry_id = request.args.get("inquiry_id", type=int)
    requested_prospect_id = request.args.get("prospect_id", type=int)
    if requested_deal_id:
        manual_phone = (deal["contact_number"] or "").strip() if deal else ""
        if manual_phone:
            manual_call_url = url_for("main.communication_manual_call", deal_id=requested_deal_id)
    elif requested_inquiry_id:
        manual_phone = (inquiry["phone"] or "").strip() if inquiry else ""
        if manual_phone:
            manual_call_url = url_for("main.communication_manual_call", inquiry_id=requested_inquiry_id)
    elif requested_prospect_id:
        manual_phone = (prospect["phone"] or "").strip() if prospect else ""
        if manual_phone:
            manual_call_url = url_for("main.communication_manual_call", prospect_id=requested_prospect_id)

    email_unread = 0
    email_message_count = 0
    if preferred_conversation_id:
        email_unread = int(db.execute(
            """SELECT COUNT(*) c FROM client_notifications
               WHERE user_id=? AND entity_type='conversation' AND entity_id=?
                 AND read_at IS NULL AND kind='CLIENT_REPLY'""",
            (g.user["id"], preferred_conversation_id),
        ).fetchone()["c"])
        email_message_count = int(db.execute(
            "SELECT COUNT(*) c FROM client_messages WHERE conversation_id=? AND channel='EMAIL'",
            (preferred_conversation_id,),
        ).fetchone()["c"])

    whatsapp_message_count = 0
    if whatsapp_conditions:
        whatsapp_message_count = int(db.execute(
            f"""SELECT COUNT(*) c FROM whatsapp_messages
                WHERE {" OR ".join(whatsapp_conditions)}""",
            whatsapp_params,
        ).fetchone()["c"])

    retell_ready = bool(
        prospect_id
        and phone
        and current_app.config.get("RETELL_API_KEY")
        and current_app.config.get("RETELL_AGENT_ID")
        and current_app.config.get("RETELL_FROM_NUMBER")
        and (prospect["status"] or "").upper() not in DEAL_ACTIVE_STATUSES
    ) if prospect else False
    call_url = url_for("main.prospect_ai_call", prospect_id=prospect_id) if retell_ready else ""

    return jsonify({
        "ok": True,
        "entries": entries,
        "call_url": call_url,
        "manual_call_url": manual_call_url,
        "email_url": email_url,
        "whatsapp_url": whatsapp_url,
        "email": email,
        "phone": phone,
        "whatsapp_number": whatsapp_number,
        "dialer_ready": retell_ready,
        "retell_ready": retell_ready,
        "email_unread": email_unread,
        "email_message_count": email_message_count,
        "whatsapp_message_count": whatsapp_message_count,
        "conversation_id": preferred_conversation_id,
    })


@bp.get("/inquiries")
@login_required
def inquiries_list():
    db = get_db()

    claimed_select = """SELECT c.id AS client_conversation_id,c.lead_id,c.owner_partner_id,c.client_name AS name,
               c.client_email AS email,c.company,c.subject,c.status,c.created_at,c.updated_at,
               c.first_response_due_at,c.first_responded_at,c.last_client_message_at,c.last_outbound_message_at,
               COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') claimed_by_name,l.status AS lead_status
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
        website_inquiries = db.execute(
            """SELECT * FROM website_inquiries
               WHERE status NOT IN ('ARCHIVED','SPAM')
               ORDER BY created_at DESC,id DESC"""
        ).fetchall()
    else:
        pid = g.partner["id"]
        unclaimed = db.execute(
            "SELECT * FROM website_inquiries WHERE status='UNCLAIMED' ORDER BY created_at ASC"
        ).fetchall()
        claimed = db.execute(
            claimed_select + " AND c.owner_partner_id=? ORDER BY c.updated_at DESC LIMIT 200", (pid,)
        ).fetchall()
        website_inquiries = db.execute(
            """SELECT * FROM website_inquiries
               WHERE (status='UNCLAIMED' OR (status='CLAIMED' AND claimed_by_partner_id=?))
               ORDER BY created_at DESC,id DESC""",
            (pid,),
        ).fetchall()

    partners = []
    if g.user["role"] == "admin":
        partners = db.execute(
            "SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL ORDER BY u.full_name"
        ).fetchall()

    now = utcnow_iso()
    for inquiry in website_inquiries:
        _ensure_deal_for_website_inquiry(
            db,
            int(inquiry["id"]),
            int(g.user["id"]),
            now,
            allow_merge=False,
        )
    db.commit()

    inquiry_ids = [int(row["id"]) for row in website_inquiries]
    workspace_deal_rows = []
    if inquiry_ids:
        placeholders = ",".join("?" for _ in inquiry_ids)
        workspace_deal_rows = db.execute(
            f"""SELECT d.* FROM deals d
                WHERE d.website_inquiry_id IN ({placeholders})
                ORDER BY d.id""",
            inquiry_ids,
        ).fetchall()
    inquiry_deals = {
        int(row["website_inquiry_id"]): row
        for row in workspace_deal_rows
        if row["website_inquiry_id"] is not None
    }
    inquiry_status_by_id = {
        int(row["id"]): (row["workflow_status"] or "").strip().upper()
        for row in website_inquiries
    }
    inquiry_deal_ids = {
        int(row["website_inquiry_id"]): int(row["id"])
        for row in workspace_deal_rows
        if row["website_inquiry_id"] is not None
        and inquiry_status_by_id.get(int(row["website_inquiry_id"]), "") in DEAL_ACTIVE_STATUSES
    }
    deal_support = _deal_card_support(db, workspace_deal_rows)

    overdue = [row for row in claimed if row["first_response_due_at"] and not row["first_responded_at"] and row["first_response_due_at"] < now]
    from .client_ops import email_receive_configured, email_send_configured
    return render_template(
        "inquiries.html", title="Website Inbox", unclaimed=unclaimed, claimed=claimed, website_inquiries=website_inquiries, partners=partners, overdue=overdue, current_time_iso=now,
        inquiry_workflow_status_labels=PROSPECT_STATUS_LABELS,
        inquiry_deal_ids=inquiry_deal_ids,
        inquiry_deals=inquiry_deals,
        email_send_ready=email_send_configured(), email_receive_ready=email_receive_configured(),
        auto_email_sync=bool(current_app.config.get("AUTO_EMAIL_SYNC")),
        response_sla_minutes=int(current_app.config.get("FIRST_RESPONSE_SLA_MINUTES", 60)),
        card_layout=_card_layout_preference(db, "inquiries"),
        **deal_support,
    )


@bp.get("/records")
@login_required
def records():
    db = get_db()
    master_records = _records_for_current_user(db)

    workflow_counts = {code: 0 for code in PROSPECT_STATUS_LABELS}
    source_counts = {"ALL": len(master_records), "RESEARCH": 0, "WEBSITE": 0, "MULTI": 0}
    for record in master_records:
        status = (record["current_status"] or "").strip().upper()
        if status in workflow_counts:
            workflow_counts[status] += 1
        source_counts[record["source_filter"]] = source_counts.get(record["source_filter"], 0) + 1

    requested_filter = (request.args.get("filter", "") or "").strip().upper()
    initial_filter = requested_filter if requested_filter in PROSPECT_STATUS_LABELS else "ALL"
    requested_source = (request.args.get("source", "") or "").strip().upper()
    initial_source = requested_source if requested_source in ("RESEARCH", "WEBSITE", "MULTI") else "ALL"

    return render_template(
        "records.html",
        title="Records & History Control",
        records=master_records,
        workflow_status_labels=PROSPECT_STATUS_LABELS,
        workflow_counts=workflow_counts,
        source_counts=source_counts,
        initial_filter=initial_filter,
        initial_source=initial_source,
    )


@bp.get("/inquiries/records")
@login_required
def inquiry_records():
    return redirect(url_for("main.records"))


@bp.get("/records/<record_key>")
@login_required
def record_detail(record_key: str):
    db = get_db()
    master_records = _records_for_current_user(db)
    record = find_master_record(master_records, record_key)
    if not record:
        abort(404)

    deal_documents: dict[int, list] = {}
    if record["deal_ids"]:
        placeholders = ",".join("?" for _ in record["deal_ids"])
        rows = db.execute(
            f"""SELECT id,deal_id,document_type,display_name,original_name,mime_type,size_bytes,created_at
                FROM deal_documents
                WHERE deal_id IN ({placeholders})
                ORDER BY deal_id,created_at DESC,id DESC""",
            record["deal_ids"],
        ).fetchall()
        for row in rows:
            deal_documents.setdefault(int(row["deal_id"]), []).append(row)

    timeline = []
    for prospect in record["prospects"]:
        timeline.append({
            "at": prospect.get("created_at") or prospect.get("recorded_date") or "",
            "title": "Prospect created",
            "description": prospect.get("name") or "",
            "kind": "research",
        })
    for inquiry in record["inquiries"]:
        timeline.append({
            "at": inquiry.get("created_at") or "",
            "title": "Website Inquiry received",
            "description": inquiry.get("source_action") or inquiry.get("source_title") or "",
            "kind": "website",
        })
    for deal in record["deals"]:
        timeline.append({
            "at": deal.get("created_at") or "",
            "title": "Became Deal",
            "description": "This client entered the Deal pipeline.",
            "kind": "deal",
        })

    activity_parts = []
    activity_params = []
    for entity_type, ids in (
        ("prospect", record["prospect_ids"]),
        ("inquiry", record["inquiry_ids"]),
        ("deal", record["deal_ids"]),
    ):
        if not ids:
            continue
        placeholders = ",".join("?" for _ in ids)
        activity_parts.append(f"(a.entity_type=? AND a.entity_id IN ({placeholders}))")
        activity_params.append(entity_type)
        activity_params.extend(ids)

    if activity_parts:
        activity_rows = db.execute(
            """SELECT a.*,COALESCE(u.full_name,'System') AS actor_name
               FROM activity_log a
               LEFT JOIN users u ON u.id=a.actor_user_id
               WHERE """ + " OR ".join(activity_parts) + """
               ORDER BY a.created_at DESC,a.id DESC""",
            activity_params,
        ).fetchall()
        for row in activity_rows:
            if row["action_type"] in ("PROSPECT_CREATED", "DEAL_CREATED"):
                continue
            timeline.append({
                "at": row["created_at"] or "",
                "title": row["description"] or row["action_type"].replace("_", " ").title(),
                "description": row["actor_name"] or "System",
                "kind": "activity",
            })

    # Master Record detail reads like a story: earliest activity first.
    timeline.sort(key=lambda item: item["at"] or "")

    return render_template(
        "record_detail.html",
        title="Record",
        record=record,
        timeline=timeline,
        workflow_status_labels=PROSPECT_STATUS_LABELS,
        deal_documents=deal_documents,
    )


@bp.get("/inquiries/records/<int:inquiry_id>")
@login_required
def inquiry_record_detail(inquiry_id: int):
    records_now = _records_for_current_user(get_db())
    for record in records_now:
        if inquiry_id in record["inquiry_ids"]:
            return redirect(url_for("main.record_detail", record_key=record["record_key"]))
    abort(404)


@bp.post("/records/delete")
@bp.post("/inquiries/records/delete")
@admin_required
def records_bulk_delete():
    validate_csrf()
    requested_keys = []
    for raw in request.form.getlist("record_keys"):
        key = (raw or "").strip()
        if key and key not in requested_keys:
            requested_keys.append(key)

    current_filter = (request.form.get("filter", "") or "").strip().upper()
    redirect_filter = current_filter if current_filter in PROSPECT_STATUS_LABELS else "ALL"
    current_source = (request.form.get("source", "") or "").strip().upper()
    redirect_source = current_source if current_source in ("RESEARCH", "WEBSITE", "MULTI") else "ALL"

    if not requested_keys:
        flash("Select at least one Record.", "warning")
        return redirect(url_for("main.records", filter=redirect_filter, source=redirect_source))

    db = get_db()
    record_map = {record["record_key"]: record for record in build_master_records(db)}
    deleted_count = 0
    protected_count = 0
    missing_count = 0
    shared_history_kept = 0

    for key in requested_keys:
        record = record_map.get(key)
        if not record:
            missing_count += 1
            continue
        if not record["can_delete"]:
            protected_count += 1
            continue

        record_deleted = False
        record_became_protected = False

        for inquiry_id in record["inquiry_ids"]:
            result = _delete_inbound_record_tree(db, inquiry_id)
            if result["protected"]:
                record_became_protected = True
                break
            if result["deleted"]:
                record_deleted = True
                shared_history_kept += int(result.get("shared_history_kept") or 0)

        if record_became_protected:
            protected_count += 1
            continue

        for prospect_id in record["prospect_ids"]:
            result = _delete_prospect_record_tree(db, prospect_id)
            if result["protected"]:
                record_became_protected = True
                break
            if result["deleted"]:
                record_deleted = True

        if record_became_protected:
            protected_count += 1
            continue

        if record_deleted:
            deleted_count += 1
        else:
            missing_count += 1

    if deleted_count:
        db.commit()
        message = f"Permanently deleted {deleted_count} inactive master Record{'s' if deleted_count != 1 else ''} and their linked source/Deal history."
        if protected_count:
            message += f" {protected_count} active pipeline Record{'s were' if protected_count != 1 else ' was'} protected."
        if shared_history_kept:
            message += f" {shared_history_kept} shared client conversation{'s were' if shared_history_kept != 1 else ' was'} preserved because other records still use them."
        if missing_count:
            message += f" {missing_count} selected Record{'s were' if missing_count != 1 else ' was'} no longer available."
        flash(message, "success" if not protected_count else "warning")
    else:
        db.rollback()
        if protected_count:
            flash("No Records were deleted. Active Deal / Demo / Proposal / Decision records are protected.", "warning")
        else:
            flash("No selected Records were available to delete.", "warning")

    return redirect(url_for("main.records", filter=redirect_filter, source=redirect_source))


@bp.post("/inquiries/<int:inquiry_id>/workflow-status")
@login_required
def inquiry_workflow_status_update(inquiry_id: int):
    validate_csrf()
    inquiry = _authorized_inquiry(inquiry_id)
    status = (request.form.get("status", "") or "").strip().upper()
    if status not in PROSPECT_STATUS_LABELS:
        return jsonify({"ok": False, "message": "Invalid Website Inquiry status."}), 400

    db = get_db()
    current_status = (inquiry["workflow_status"] or "").strip().upper()
    leaving_deal_pipeline = current_status in DEAL_ACTIVE_STATUSES and status in DEAL_PRE_STATUS_STATUSES
    if leaving_deal_pipeline and (request.form.get("confirm_leave_deals", "") or "").strip().lower() != "yes":
        return jsonify({
            "ok": False,
            "error": "confirmation_required",
            "message": "Confirm the backward Status change before removing the linked Deal from Deals.",
        }), 409

    now = utcnow_iso()
    deal_created = False
    deal_id = None
    db.execute(
        "UPDATE website_inquiries SET workflow_status=?,updated_at=? WHERE id=?",
        (status, now, inquiry_id),
    )
    if status != current_status:
        log_activity(
            "WORKFLOW_STATUS_CHANGED",
            "inquiry",
            inquiry_id,
            f"Website Inquiry status changed from {PROSPECT_STATUS_LABELS.get(current_status, current_status)} to {PROSPECT_STATUS_LABELS.get(status, status)}.",
            {"from": current_status, "to": status},
        )
    linked_deal = db.execute(
        "SELECT id FROM deals WHERE website_inquiry_id=? LIMIT 1",
        (inquiry_id,),
    ).fetchone()
    deal_id = int(linked_deal["id"]) if linked_deal else None
    if status in DEAL_ACTIVE_STATUSES and deal_id is None:
        deal_id, deal_created = _ensure_deal_for_website_inquiry(db, inquiry_id, g.user["id"], now)
    if deal_id is not None:
        if status in DEAL_ACTIVE_STATUSES:
            if current_status not in DEAL_ACTIVE_STATUSES:
                _mark_deal_became(db, deal_id, now)
            db.execute("UPDATE deals SET status=?,updated_at=? WHERE id=?", (status, now, deal_id))
            deal_id = _reconcile_deal_sources_on_activation(db, deal_id, now)
            _mark_deal_became(db, deal_id, now)
        _sync_deal_source_statuses(db, deal_id, status, now)
    db.commit()
    if status in DEAL_ACTIVE_STATUSES and current_status not in DEAL_ACTIVE_STATUSES and deal_id is not None:
        _sync_calendar_for_activated_deal(db, deal_id)
    return jsonify({
        "ok": True,
        "status": status,
        "deal_id": deal_id,
        "deal_created": deal_created,
        "removed_from_deals": status in DEAL_PRE_STATUS_STATUSES,
    })


@bp.post("/inquiries/<int:inquiry_id>/notes-after-conversation")
@login_required
def inquiry_notes_after_conversation_update(inquiry_id: int):
    validate_csrf()
    _authorized_inquiry(inquiry_id)
    value = (request.form.get("value", "") or "").strip()[:3000]
    db = get_db()
    now = utcnow_iso()
    db.execute(
        "UPDATE website_inquiries SET notes_after_conversation=?,updated_at=? WHERE id=?",
        (value, now, inquiry_id),
    )
    db.execute(
        "UPDATE deals SET notes_after_conversation=?,updated_at=? WHERE website_inquiry_id=?",
        (value, now, inquiry_id),
    )
    db.execute(
        """UPDATE prospects
           SET notes_after_conversation=?,updated_at=?
           WHERE id IN (
             SELECT prospect_id FROM deals
             WHERE website_inquiry_id=? AND prospect_id IS NOT NULL
           )""",
        (value, now, inquiry_id),
    )
    db.commit()
    return jsonify({"ok": True, "value": value})


@bp.post("/inquiries/<int:inquiry_id>/delete")
@admin_required
def inquiry_delete(inquiry_id: int):
    validate_csrf()
    inquiry = _authorized_inquiry(inquiry_id)
    db = get_db()
    linked_deal = db.execute(
        "SELECT id,prospect_id,became_deal_at FROM deals WHERE website_inquiry_id=? LIMIT 1",
        (inquiry_id,),
    ).fetchone()
    workflow_status = (inquiry["workflow_status"] or "").strip().upper()
    linked_shared_source = bool(linked_deal and linked_deal["prospect_id"] is not None)
    if (
        inquiry["status"] == "CLAIMED"
        or inquiry["client_conversation_id"]
        or workflow_status in DEAL_ACTIVE_STATUSES
        or linked_shared_source
    ):
        flash("This Website Inquiry has linked Deal or client history and cannot be permanently deleted.", "warning")
        return redirect(url_for("main.inquiries_list"))

    if linked_deal:
        db.execute("DELETE FROM deals WHERE id=?", (linked_deal["id"],))
    db.execute(
        "DELETE FROM client_notifications WHERE entity_type='inquiry' AND entity_id=?",
        (inquiry_id,),
    )
    db.execute("DELETE FROM website_inquiries WHERE id=?", (inquiry_id,))
    db.commit()
    flash("Website Inquiry deleted.", "success")
    return redirect(url_for("main.inquiries_list"))


@bp.get("/inquiries/<int:inquiry_id>")
@login_required
def inquiry_detail(inquiry_id: int):
    inquiry = _authorized_inquiry(inquiry_id)
    if inquiry["status"] == "CLAIMED" and inquiry["client_conversation_id"]:
        return redirect(url_for("main.client_conversation", conversation_id=inquiry["client_conversation_id"]))
    partners = []
    if g.user["role"] == "admin":
        partners = get_db().execute(
            "SELECT p.id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id WHERE p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL ORDER BY u.full_name"
        ).fetchall()
    matches, _normalized = duplicate_candidates({
        "company_name": inquiry["company"], "contact_name": inquiry["name"], "email": inquiry["email"],
        "phone": "", "website": "",
    })
    duplicate_leads = []
    duplicate_warning = bool(matches)
    # Full duplicate details are Founder-only. Partners only get a simple warning.
    if g.user["role"] == "admin":
        for row, reasons in matches[:5]:
            detail = get_db().execute(
                """SELECT l.id,l.company_name,l.contact_name,l.status,
                          COALESCE(u.full_name,NULLIF(p.historical_name,''),'Deleted Partner') owner_name
                   FROM leads l JOIN partners p ON p.id=l.owner_partner_id LEFT JOIN users u ON u.id=p.user_id WHERE l.id=?""",
                (row["id"],),
            ).fetchone()
            if detail:
                duplicate_leads.append((detail, reasons))
    mark_client_notifications_read(entity_type="inquiry", entity_id=inquiry_id)
    return render_template(
        "inquiry_detail.html", title="New Inquiry", inquiry=inquiry, partners=partners,
        duplicate_leads=duplicate_leads, duplicate_warning=duplicate_warning,
    )


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
    flash("Inquiry removed from Inbox.", "success")
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
        """SELECT m.*,u.full_name sent_by_name FROM client_messages m
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
        flash("RSF could not send that email. Check the email setup and try again.", "error")
    else:
        flash("Reply sent from the official RSF email.", "success")
    return redirect(url_for("main.client_conversation", conversation_id=conversation_id))


@bp.post("/clients/sync-email")
@admin_required
def client_sync_email():
    from .client_ops import sync_inbound_email
    try:
        result = sync_inbound_email()
    except RuntimeError as exc:
        flash(str(exc), "warning")
    except Exception:
        current_app.logger.exception("Client email sync failed")
        flash("Email sync failed. Try again later.", "error")
    else:
        extra = f" {result.get('bounced', 0)} bounce(s) detected." if result.get("bounced") else ""
        flash(f"Email sync finished. {result['imported']} new message(s).{extra}", "success")
    return redirect(request.referrer or url_for("main.inquiries_list"))


@bp.post("/admin/recovery/upload-preserved-file")
@admin_required
def recovery_upload_preserved_file():
    """One-time, Founder-only recovery path for a deleted Render deployment.

    The route is disabled unless RSF_RECOVERY_UPLOAD_ENABLED=1 is present in the
    production environment. It can only fill the database-backed blob for a file
    record that already exists after the trusted local-database migration.
    """
    if os.environ.get("RSF_RECOVERY_UPLOAD_ENABLED", "0").strip() != "1":
        abort(404)
    kind = (request.form.get("kind") or "").strip()
    stored_name = (request.form.get("stored_name") or "").strip()
    if not stored_name or stored_name != Path(stored_name).name or len(stored_name) > 255:
        abort(400, description="Invalid preserved filename.")
    uploaded = request.files.get("file")
    if not uploaded:
        abort(400, description="Preserved file is required.")
    data = uploaded.read()
    if not data or len(data) > current_app.config.get("MAX_CONTENT_LENGTH", 32 * 1024 * 1024):
        abort(400, description="Invalid preserved file data.")
    db = get_db()
    if kind == "message_uploads":
        result = db.execute(
            "UPDATE message_attachments SET data_blob=? WHERE stored_name=?",
            (data, stored_name),
        )
    elif kind == "client_attachments":
        result = db.execute(
            "UPDATE client_attachments SET data_blob=? WHERE stored_name=?",
            (data, stored_name),
        )
    elif kind == "profile_pictures":
        result = db.execute(
            "UPDATE users SET avatar_data=? WHERE avatar_stored_name=?",
            (data, stored_name),
        )
    else:
        abort(400, description="Unknown preserved file category.")
    if result.rowcount != 1:
        abort(404, description="No matching preserved file record exists.")
    db.commit()
    return jsonify(ok=True, stored_name=stored_name, size_bytes=len(data))
