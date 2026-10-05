from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime, timezone

from flask import current_app

from .db import using_postgres
from .whatsapp_ops import whatsapp_messaging_configured
from .twilio_manual_call_ops import manual_call_configured


SERVICE_DEFINITIONS = (
    ("render", "Render Hosting"),
    ("database", "Database"),
    ("gmail", "RSF Gmail"),
    ("calendar", "Google Calendar / Meet"),
    ("whatsapp", "WhatsApp"),
    ("twilio", "Twilio Voice"),
)


def _setting_value(db, key: str, default: str = "") -> str:
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return str(row["value"]) if row else default


def _decimal_or_none(value: str):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    return amount.quantize(Decimal("0.01"))


def validate_manual_money(value: str, *, allow_zero: bool = True) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Use numbers only for costs and budgets.") from exc
    if amount < 0 or (not allow_zero and amount == 0):
        raise ValueError("Costs cannot be negative and budgets must be greater than zero.")
    if amount > Decimal("999999999.99"):
        raise ValueError("That cost or budget is too large.")
    return f"{amount.quantize(Decimal('0.01'))}"


def _format_bytes(size_bytes: int) -> str:
    size = max(0, int(size_bytes or 0))
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if value < 1024 or candidate == units[-1]:
            break
        value /= 1024
    return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"


def _database_usage(db) -> str:
    try:
        if using_postgres():
            row = db.execute("SELECT pg_database_size(current_database()) AS size_bytes").fetchone()
            return f"{_format_bytes(int(row['size_bytes'] or 0))} database size"
        path = Path(current_app.config["DATABASE"])
        return f"{_format_bytes(path.stat().st_size if path.exists() else 0)} local database"
    except Exception:
        return "Usage unavailable"


def _status_label(connected: bool, configured: bool = False) -> tuple[str, str]:
    if connected:
        return "Connected", "connected"
    if configured:
        return "Ready to connect", "ready"
    return "Not connected", "off"


def _budget_status(current_cost, monthly_budget):
    if current_cost is None or monthly_budget is None:
        return {
            "label": "NOT SET",
            "class_name": "unset",
            "percentage": None,
            "remaining": None,
            "overage": None,
        }
    if monthly_budget <= 0:
        return {
            "label": "NOT SET",
            "class_name": "unset",
            "percentage": None,
            "remaining": None,
            "overage": None,
        }
    percentage = (current_cost / monthly_budget) * Decimal("100")
    remaining = max(monthly_budget - current_cost, Decimal("0"))
    overage = max(current_cost - monthly_budget, Decimal("0"))
    if percentage < 70:
        label, class_name = "NORMAL", "normal"
    elif percentage < 85:
        label, class_name = "WARNING", "warning"
    elif percentage < 100:
        label, class_name = "NEAR LIMIT", "near"
    elif percentage == 100:
        label, class_name = "BUDGET REACHED", "reached"
    else:
        label, class_name = "OVERAGE", "overage"
    return {
        "label": label,
        "class_name": class_name,
        "percentage": percentage.quantize(Decimal("0.1")),
        "remaining": remaining.quantize(Decimal("0.01")),
        "overage": overage.quantize(Decimal("0.01")),
    }


def build_integration_billing_dashboard(db, *, gmail_status: dict, calendar_status: dict) -> dict:
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")

    email_row = db.execute(
        "SELECT COUNT(*) AS c FROM client_messages WHERE channel='EMAIL' AND substr(created_at,1,7)=?",
        (month_key,),
    ).fetchone()
    calendar_row = db.execute(
        "SELECT COUNT(*) AS c FROM deals WHERE COALESCE(google_calendar_synced_at,'')<>'' AND substr(google_calendar_synced_at,1,7)=?",
        (month_key,),
    ).fetchone()
    whatsapp_row = db.execute(
        "SELECT COUNT(*) AS c FROM whatsapp_messages WHERE substr(created_at,1,7)=?",
        (month_key,),
    ).fetchone()
    twilio_row = db.execute(
        """SELECT COUNT(*) AS calls,COALESCE(SUM(duration_seconds),0) AS seconds
           FROM manual_client_calls
           WHERE provider='TWILIO' AND substr(created_at,1,7)=?""",
        (month_key,),
    ).fetchone()

    gmail_label, gmail_class = _status_label(
        bool(gmail_status.get("connected")),
        bool(gmail_status.get("oauth_configured")),
    )
    calendar_label, calendar_class = _status_label(
        bool(calendar_status.get("connected")),
        bool(calendar_status.get("oauth_configured")),
    )

    render_active = bool(
        os.environ.get("RENDER")
        or os.environ.get("RENDER_SERVICE_ID")
        or current_app.config.get("RENDER_SERVICE_ID")
    )
    render_label = "Active" if render_active else "Not detected"
    render_class = "connected" if render_active else "off"

    database_label = "PostgreSQL active" if using_postgres() else "Local SQLite"
    database_class = "connected" if using_postgres() else "ready"

    whatsapp_ready = whatsapp_messaging_configured()
    whatsapp_label = "Configured" if whatsapp_ready else "Not configured"
    whatsapp_class = "connected" if whatsapp_ready else "off"

    twilio_ready = manual_call_configured()
    twilio_label = "Configured" if twilio_ready else "Not configured"
    twilio_class = "connected" if twilio_ready else "off"

    seconds = int(twilio_row["seconds"] or 0)
    minutes = seconds / 60
    service_runtime = {
        "render": {
            "status": render_label,
            "status_class": render_class,
            "usage": "Provider metrics not connected",
            "usage_source": "Render billing/usage API is not connected to RSF.",
        },
        "database": {
            "status": database_label,
            "status_class": database_class,
            "usage": _database_usage(db),
            "usage_source": "Measured automatically by RSF.",
        },
        "gmail": {
            "status": gmail_label,
            "status_class": gmail_class,
            "usage": f"{int(email_row['c'] or 0)} email message(s) this month",
            "usage_source": "RSF-tracked email records, not Google quota usage.",
        },
        "calendar": {
            "status": calendar_label,
            "status_class": calendar_class,
            "usage": f"{int(calendar_row['c'] or 0)} deal sync(s) this month",
            "usage_source": "RSF-tracked Deal syncs, not Google API quota usage.",
        },
        "whatsapp": {
            "status": whatsapp_label,
            "status_class": whatsapp_class,
            "usage": f"{int(whatsapp_row['c'] or 0)} message(s) this month",
            "usage_source": "RSF-tracked WhatsApp messages, not Meta billing usage.",
        },
        "twilio": {
            "status": twilio_label,
            "status_class": twilio_class,
            "usage": f"{int(twilio_row['calls'] or 0)} call(s) · {minutes:.1f} min this month",
            "usage_source": "RSF-tracked call records, not Twilio invoice data.",
        },
    }

    rows = []
    total_cost = Decimal("0")
    total_budget = Decimal("0")
    total_remaining = Decimal("0")
    total_overage = Decimal("0")
    cost_count = 0
    budget_count = 0
    paired_count = 0

    for slug, name in SERVICE_DEFINITIONS:
        prefix = f"integration_billing.{slug}."
        cost_raw = _setting_value(db, prefix + "current_cost")
        budget_raw = _setting_value(db, prefix + "monthly_budget")
        reset_raw = _setting_value(db, prefix + "billing_reset")
        current_cost = _decimal_or_none(cost_raw)
        monthly_budget = _decimal_or_none(budget_raw)
        budget_state = _budget_status(current_cost, monthly_budget)

        if current_cost is not None:
            total_cost += current_cost
            cost_count += 1
        if monthly_budget is not None:
            total_budget += monthly_budget
            budget_count += 1
        if budget_state["remaining"] is not None:
            total_remaining += budget_state["remaining"]
            total_overage += budget_state["overage"]
            paired_count += 1

        rows.append({
            "slug": slug,
            "name": name,
            **service_runtime[slug],
            "current_cost": current_cost,
            "current_cost_raw": cost_raw,
            "monthly_budget": monthly_budget,
            "monthly_budget_raw": budget_raw,
            "billing_reset": reset_raw,
            "budget_state": budget_state,
        })

    service_count = len(SERVICE_DEFINITIONS)
    return {
        "rows": rows,
        "month_label": datetime.now(timezone.utc).strftime("%B %Y"),
        "summary": {
            "current_cost": total_cost.quantize(Decimal("0.01")) if cost_count else None,
            "monthly_budget": total_budget.quantize(Decimal("0.01")) if budget_count else None,
            "remaining": total_remaining.quantize(Decimal("0.01")) if paired_count else None,
            "overage": total_overage.quantize(Decimal("0.01")) if paired_count else None,
            "paired_count": paired_count,
            "cost_count": cost_count,
            "budget_count": budget_count,
            "service_count": service_count,
            "cost_complete": cost_count == service_count,
            "budget_complete": budget_count == service_count,
        },
    }
