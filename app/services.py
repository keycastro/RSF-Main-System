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


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def setting(key: str, default: str = "") -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def log_activity(action_type: str, entity_type: str, entity_id: int | None, description: str, metadata: dict | None = None, actor_user_id: int | None = None) -> None:
    db = get_db()
    actor = actor_user_id if actor_user_id is not None else (g.user["id"] if getattr(g, "user", None) else None)
    actor_name = ""
    if actor is not None:
        row = db.execute("SELECT full_name FROM users WHERE id=?", (actor,)).fetchone()
        actor_name = row["full_name"] if row else ""
    db.execute(
        "INSERT INTO activity_log(actor_user_id,actor_name_snapshot,action_type,entity_type,entity_id,description,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (actor, actor_name, action_type, entity_type, entity_id, description[:500], json.dumps(metadata or {}, separators=(",", ":")), utcnow_iso()),
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
