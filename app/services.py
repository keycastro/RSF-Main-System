from __future__ import annotations

import ipaddress
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

from flask import g

from .db import get_db

PIPELINE = ["NEW", "CONTACTED", "QUALIFIED", "DEMO_BOOKED", "PROPOSAL", "WON", "LOST"]
PARTNER_ALLOWED_STATUSES = {"NEW", "CONTACTED", "QUALIFIED", "DEMO_BOOKED", "LOST"}
PAYMENT_STATUSES = ["UNPAID", "PARTIALLY_PAID", "PAID", "REFUNDED_ADJUSTED"]
RESOURCE_CATEGORIES = [
    "Sales Script", "Outreach Template", "Offer Information", "Demo Link", "FAQ",
    "Qualification Questions", "Objection Handling", "Company Information", "Pricing Document",
]


def server_utc_now() -> datetime:
    """Authoritative RSF current time from the server/system UTC clock."""
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return server_utc_now().replace(microsecond=0).isoformat()


def normalize_text(value: str | None) -> str:
    """Normalize names for matching without dropping non-ASCII text accidentally."""
    raw = unicodedata.normalize("NFKD", (value or "").strip().casefold())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = "".join(ch if ch.isalnum() else " " for ch in raw)
    return " ".join(raw.split())[:240]


def normalize_email(value: str | None) -> str:
    return (value or "").strip().casefold()[:254]


def normalize_phone(value: str | None) -> str:
    raw = (value or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        return "+" + digits[:20]
    return digits[:20]


def file_signature_matches(suffix: str, data: bytes) -> bool:
    """Basic file-content check for allowed business uploads."""
    suffix = (suffix or "").lower()
    head = bytes(data[:4096])
    if suffix == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if suffix == ".pdf":
        return head.startswith(b"%PDF-")
    if suffix in {".doc", ".xls", ".ppt"}:
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if suffix in {".docx", ".xlsx", ".pptx", ".zip"}:
        return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if suffix == ".rtf":
        return head.lstrip().startswith(b"{\\rtf")
    if suffix in {".txt", ".csv"}:
        return b"\x00" not in head
    return False


def normalize_domain(value: str | None) -> str:
    raw = (value or "").strip().casefold()
    if not raw or any(ch.isspace() for ch in raw):
        return ""
    candidate = raw if "://" in raw else "https://" + raw
    try:
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            return ""
        host = (parsed.hostname or "").strip(".").casefold()
        if not host:
            return ""
        if host.startswith("www."):
            host = host[4:]
        try:
            ipaddress.ip_address(host)
            return host[:240]
        except ValueError:
            pass
        ascii_host = host.encode("idna").decode("ascii")
        labels = ascii_host.split(".")
        if len(labels) < 2 or any(not label or len(label) > 63 for label in labels):
            return ""
        label_re = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", re.I)
        if any(not label_re.fullmatch(label) for label in labels):
            return ""
        return ascii_host[:240]
    except (ValueError, UnicodeError):
        return ""


def normalize_local_datetime(value: str | None, label: str = "Date and time") -> str:
    raw = (value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not valid.") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def normalize_date(value: str | None, label: str = "Date") -> str:
    raw = (value or "").strip()
    try:
        return date.fromisoformat(raw).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not valid.") from exc


def money_to_cents(value: str | int | None) -> int:
    if isinstance(value, int):
        return value
    raw = (value or "").strip().replace(",", "")
    if raw == "":
        return 0
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Enter a valid amount.") from exc
    if not amount.is_finite():
        raise ValueError("Enter a valid amount.")
    if amount < 0:
        raise ValueError("Amount cannot be negative.")
    # Guard against accidentally entering absurd values or exhausting SQLite integer range.
    if amount > Decimal("999999999999.99"):
        raise ValueError("Amount is too large.")
    return int(amount * 100)


def signed_money_to_cents(value: str | None) -> int:
    raw = (value or "0").strip().replace(",", "")
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Enter a valid adjustment amount.") from exc
    if not amount.is_finite() or abs(amount) > Decimal("999999999999.99"):
        raise ValueError("Enter a valid adjustment amount.")
    return int(amount * 100)


def commission_amount(qualifying_cents: int, rate_bp: int, adjustment_cents: int = 0) -> int:
    base = (Decimal(qualifying_cents) * Decimal(rate_bp) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(0, int(base) + int(adjustment_cents))


def commission_change_for_revenue(revenue_change_cents: int, rate_bp: int) -> int:
    """Calculate a signed commission change from a signed revenue change."""
    value = (Decimal(revenue_change_cents) * Decimal(rate_bp) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(value)


def setting(key: str, default: str = "") -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def log_activity(action_type: str, entity_type: str, entity_id: int | None, description: str, metadata: dict | None = None, actor_user_id: int | None = None) -> None:
    db = get_db()
    actor = actor_user_id if actor_user_id is not None else (g.user["id"] if getattr(g, "user", None) else None)
    db.execute(
        "INSERT INTO activity_log(actor_user_id,action_type,entity_type,entity_id,description,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)",
        (actor, action_type, entity_type, entity_id, description[:500], json.dumps(metadata or {}, separators=(",", ":")), utcnow_iso()),
    )


def touch_lead(lead_id: int) -> None:
    get_db().execute("UPDATE leads SET last_activity_at=? WHERE id=?", (utcnow_iso(), lead_id))


def duplicate_candidates(data: dict, exclude_lead_id: int | None = None):
    """Return probable duplicates only when at least two prospect signals agree.

    This avoids the old single-field behavior where one shared company domain could
    block a valid contact. It also keeps matching useful for first-registration
    ownership by combining company, contact, email, phone, and domain evidence.
    """
    db = get_db()
    fields = {
        "company_norm": normalize_text(data.get("company_name")),
        "contact_norm": normalize_text(data.get("contact_name")),
        "email_norm": normalize_email(data.get("email")),
        "phone_norm": normalize_phone(data.get("phone")),
        "website_domain": normalize_domain(data.get("website")),
    }
    sql = "SELECT id, owner_partner_id, company_norm, contact_norm, email_norm, phone_norm, website_domain FROM leads"
    params: tuple = ()
    if exclude_lead_id is not None:
        sql += " WHERE id<>?"
        params = (exclude_lead_id,)
    rows = db.execute(sql, params).fetchall()

    matches = []
    weights = {"email": 4, "phone": 4, "company": 3, "website/domain": 2, "contact": 2}
    for row in rows:
        signals = {
            "company": bool(fields["company_norm"] and fields["company_norm"] == row["company_norm"]),
            "contact": bool(fields["contact_norm"] and fields["contact_norm"] == row["contact_norm"]),
            "email": bool(fields["email_norm"] and fields["email_norm"] == row["email_norm"]),
            "phone": bool(fields["phone_norm"] and fields["phone_norm"] == row["phone_norm"]),
            "website/domain": bool(fields["website_domain"] and fields["website_domain"] == row["website_domain"]),
        }
        reasons = [name for name, matched in signals.items() if matched]
        if len(reasons) < 2:
            continue
        # Two agreeing practical fields are required. This deliberately prevents
        # a domain, phone, or email by itself from deciding ownership.
        score = sum(weights[name] for name in reasons)
        matches.append((row, reasons, score))

    matches.sort(key=lambda item: (-item[2], item[0]["id"]))
    return [(row, reasons) for row, reasons, _score in matches], fields



def transfer_lead_ownership(lead_id: int, new_partner_id: int, *, allow_sale_history: bool = False) -> dict:
    """Move active CRM work for one lead to an active Partner.

    Sales and commission rows are never changed. When allow_sale_history is False,
    ownership is locked after a sale. The delete-account flow may set it True so
    active client work can continue while sale history stays with the old Partner.
    """
    db = get_db()
    lead = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        raise ValueError("Lead not found.")
    target = db.execute(
        """SELECT p.id,p.user_id,u.full_name FROM partners p JOIN users u ON u.id=p.user_id
           WHERE p.id=? AND p.active=1 AND u.active=1 AND p.account_deleted_at IS NULL""",
        (new_partner_id,),
    ).fetchone()
    if not target:
        raise ValueError("That Partner is not available.")
    old_partner_id = int(lead["owner_partner_id"])
    if old_partner_id == int(new_partner_id):
        return {"changed": False, "old_partner_id": old_partner_id, "new_partner_id": int(new_partner_id), "target_name": target["full_name"]}
    if not allow_sale_history and db.execute("SELECT 1 FROM sales WHERE lead_id=?", (lead_id,)).fetchone():
        raise ValueError("This Lead already has a sale. Its owner cannot be changed here.")

    now = utcnow_iso()
    db.execute("UPDATE leads SET owner_partner_id=?,last_activity_at=? WHERE id=?", (new_partner_id, now, lead_id))
    db.execute("UPDATE followups SET owner_partner_id=?,updated_at=? WHERE lead_id=? AND status='OPEN'", (new_partner_id, now, lead_id))
    db.execute("UPDATE client_conversations SET owner_partner_id=?,updated_at=? WHERE lead_id=? AND status='ACTIVE'", (new_partner_id, now, lead_id))
    db.execute("UPDATE website_inquiries SET claimed_by_partner_id=?,updated_at=? WHERE lead_id=? AND status='CLAIMED'", (new_partner_id, now, lead_id))

    old_user = db.execute("SELECT user_id FROM partners WHERE id=?", (old_partner_id,)).fetchone()
    new_user_id = target["user_id"]
    conversations = db.execute(
        "SELECT id FROM client_conversations WHERE lead_id=? AND status='ACTIVE' ORDER BY id",
        (lead_id,),
    ).fetchall()
    inquiry_ids = db.execute(
        "SELECT id FROM website_inquiries WHERE lead_id=? AND status='CLAIMED'",
        (lead_id,),
    ).fetchall()
    if old_user and old_user["user_id"]:
        for row in conversations:
            db.execute(
                """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
                   WHERE user_id=? AND entity_type='conversation' AND entity_id=?""",
                (now, old_user["user_id"], row["id"]),
            )
        for row in inquiry_ids:
            db.execute(
                """UPDATE client_notifications SET read_at=COALESCE(read_at,?)
                   WHERE user_id=? AND entity_type='inquiry' AND entity_id=?""",
                (now, old_user["user_id"], row["id"]),
            )
    if new_user_id:
        for row in conversations:
            exists = db.execute(
                """SELECT 1 FROM client_notifications WHERE user_id=? AND kind='CLIENT_REASSIGNED'
                   AND entity_type='conversation' AND entity_id=? AND read_at IS NULL LIMIT 1""",
                (new_user_id, row["id"]),
            ).fetchone()
            if not exists:
                db.execute(
                    """INSERT INTO client_notifications(user_id,kind,entity_type,entity_id,title,body,created_at)
                       VALUES (?,'CLIENT_REASSIGNED','conversation',?,?,'This client is now assigned to you.',?)""",
                    (new_user_id, row["id"], f"Client moved: {lead['company_name']}", now),
                )
    return {
        "changed": True,
        "old_partner_id": old_partner_id,
        "new_partner_id": int(new_partner_id),
        "target_name": target["full_name"],
    }


def validate_sale_amounts(deal_cents: int, invoiced_cents: int, collected_cents: int, qualifying_cents: int, payment_status: str) -> list[str]:
    """Return simple business-rule errors for sale money fields."""
    errors: list[str] = []
    if invoiced_cents > deal_cents:
        errors.append("Invoiced amount cannot be more than the deal amount.")
    if collected_cents > invoiced_cents:
        errors.append("Collected amount cannot be more than the invoiced amount.")
    if qualifying_cents > collected_cents:
        errors.append("Commission revenue cannot be more than the collected amount.")
    if payment_status == "UNPAID" and collected_cents != 0:
        errors.append("Unpaid sales must have $0 collected.")
    if payment_status == "PAID" and (invoiced_cents <= 0 or collected_cents != invoiced_cents):
        errors.append("Paid sales need a full invoiced amount and full payment.")
    if payment_status == "PARTIALLY_PAID" and not (0 < collected_cents < invoiced_cents):
        errors.append("Partially paid sales need some payment, but not the full amount.")
    if payment_status == "REFUNDED_ADJUSTED" and collected_cents > invoiced_cents:
        errors.append("Adjusted collected amount cannot be more than the invoiced amount.")
    return errors

def create_commission_for_sale(sale_id: int, partner_id: int, qualifying_cents: int):
    db = get_db()
    partner = db.execute(
        """SELECT p.id, cs.name, cs.rate_bp FROM partners p
           JOIN commission_stages cs ON cs.id=p.commission_stage_id WHERE p.id=?""",
        (partner_id,),
    ).fetchone()
    if not partner:
        raise ValueError("Partner not found.")
    now = utcnow_iso()
    amount = commission_amount(qualifying_cents, partner["rate_bp"])
    cur = db.execute(
        """INSERT INTO commissions(sale_id,partner_id,stage_name_snapshot,rate_bp_snapshot,qualifying_revenue_cents,commission_amount_cents,status,created_at,updated_at)
           VALUES (?,?,?,?,?,?,'PENDING',?,?)""",
        (sale_id, partner_id, partner["name"], partner["rate_bp"], qualifying_cents, amount, now, now),
    )
    return cur.lastrowid


def sync_pending_commission(sale_id: int, qualifying_cents: int) -> None:
    db = get_db()
    commission = db.execute("SELECT * FROM commissions WHERE sale_id=?", (sale_id,)).fetchone()
    if not commission:
        return
    if commission["status"] != "PENDING":
        if qualifying_cents != commission["qualifying_revenue_cents"]:
            raise ValueError("Commission revenue cannot change after the commission is approved.")
        return
    amount = commission_amount(qualifying_cents, commission["rate_bp_snapshot"], commission["adjustment_cents"])
    db.execute(
        "UPDATE commissions SET qualifying_revenue_cents=?, commission_amount_cents=?, updated_at=? WHERE id=?",
        (qualifying_cents, amount, utcnow_iso(), commission["id"]),
    )
