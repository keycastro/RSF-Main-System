from __future__ import annotations

import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone

from flask import current_app

from .db import using_postgres
from .whatsapp_ops import whatsapp_messaging_configured
from .twilio_manual_call_ops import current_month_usage as twilio_current_month_usage, manual_call_configured


SERVICE_DEFINITIONS = (
    ("render", "Render Hosting"),
    ("database", "Database"),
    ("gmail", "Gmail"),
    ("calendar", "Google Meet"),
    ("whatsapp", "WhatsApp Business"),
    ("twilio", "Twilio"),
    ("retell", "Retell AI"),
)


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
            return f"{_format_bytes(int(row['size_bytes'] or 0))} used"
        path = Path(current_app.config["DATABASE"])
        return f"{_format_bytes(path.stat().st_size if path.exists() else 0)} used"
    except Exception:
        return "Not available"


def _status_label(connected: bool, configured: bool = False) -> tuple[str, str]:
    if connected:
        return "Connected", "connected"
    if configured:
        return "Ready", "ready"
    return "Not connected", "off"


def _money_text(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return "Not available"
    code = (currency or "").upper().strip()
    value = amount.quantize(Decimal("0.01"))
    return f"{code} {value}" if code else f"{value}"


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
    retell_row = db.execute(
        """SELECT COUNT(*) AS calls
           FROM ai_sales_calls
           WHERE substr(created_at,1,7)=?""",
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
    render_label = "Active" if render_active else "Not active"
    render_class = "connected" if render_active else "off"

    database_label = "Active" if using_postgres() else "Local"
    database_class = "connected" if using_postgres() else "ready"

    whatsapp_ready = whatsapp_messaging_configured()
    whatsapp_label = "Ready" if whatsapp_ready else "Not set up"
    whatsapp_class = "connected" if whatsapp_ready else "off"

    twilio_ready = manual_call_configured()
    twilio_label = "Ready" if twilio_ready else "Not set up"
    twilio_class = "connected" if twilio_ready else "off"

    retell_ready = bool(
        current_app.config.get("RETELL_API_KEY")
        and current_app.config.get("RETELL_AGENT_ID")
        and current_app.config.get("RETELL_FROM_NUMBER")
    )
    retell_label = "Ready" if retell_ready else "Not set up"
    retell_class = "connected" if retell_ready else "off"

    email_count = int(email_row["c"] or 0)
    calendar_count = int(calendar_row["c"] or 0)
    whatsapp_count = int(whatsapp_row["c"] or 0)
    retell_count = int(retell_row["calls"] or 0)

    rsf_twilio_calls = int(twilio_row["calls"] or 0)
    rsf_twilio_minutes = (int(twilio_row["seconds"] or 0) / 60)
    twilio_provider = twilio_current_month_usage() if twilio_ready else {"available": False}

    if twilio_provider.get("calls") is not None and twilio_provider.get("minutes") is not None:
        twilio_calls = int(twilio_provider["calls"])
        twilio_minutes = float(twilio_provider["minutes"])
        twilio_usage_source = "Usage comes from Twilio."
    else:
        twilio_calls = rsf_twilio_calls
        twilio_minutes = rsf_twilio_minutes
        twilio_usage_source = "Usage comes from RSF call records."

    minutes_text = f"{twilio_minutes:.1f}".rstrip("0").rstrip(".")

    twilio_cost = None
    twilio_currency = ""
    if twilio_provider.get("available") and twilio_provider.get("cost") is not None:
        twilio_cost = Decimal(str(twilio_provider["cost"]))
        twilio_currency = str(twilio_provider.get("currency") or "").upper()

    service_runtime = {
        "render": {
            "status": render_label,
            "status_class": render_class,
            "usage": "Usage not available",
            "usage_source": "Render usage is not connected to this dashboard.",
            "cost": None,
            "cost_currency": "",
            "cost_source": "Render billing is not connected to this dashboard.",
        },
        "database": {
            "status": database_label,
            "status_class": database_class,
            "usage": _database_usage(db),
            "usage_source": "Measured by RSF.",
            "cost": None,
            "cost_currency": "",
            "cost_source": "Database billing is not connected to this dashboard.",
        },
        "gmail": {
            "status": gmail_label,
            "status_class": gmail_class,
            "usage": f"{email_count} {'email' if email_count == 1 else 'emails'}",
            "usage_source": "Based on emails recorded in RSF.",
            "cost": None,
            "cost_currency": "",
            "cost_source": "Google billing is not connected to this dashboard.",
        },
        "calendar": {
            "status": calendar_label,
            "status_class": calendar_class,
            "usage": f"{calendar_count} {'calendar sync' if calendar_count == 1 else 'calendar syncs'}",
            "usage_source": "Based on calendar syncs recorded in RSF.",
            "cost": None,
            "cost_currency": "",
            "cost_source": "Google billing is not connected to this dashboard.",
        },
        "whatsapp": {
            "status": whatsapp_label,
            "status_class": whatsapp_class,
            "usage": f"{whatsapp_count} {'message' if whatsapp_count == 1 else 'messages'}",
            "usage_source": "Based on WhatsApp messages recorded in RSF.",
            "cost": None,
            "cost_currency": "",
            "cost_source": "WhatsApp billing is not connected to this dashboard.",
        },
        "twilio": {
            "status": twilio_label,
            "status_class": twilio_class,
            "usage": f"{twilio_calls} {'call' if twilio_calls == 1 else 'calls'} · {minutes_text} min",
            "usage_source": twilio_usage_source,
            "cost": twilio_cost,
            "cost_currency": twilio_currency,
            "cost_source": (
                "Cost comes from Twilio."
                if twilio_cost is not None
                else (twilio_provider.get("reason") or "Twilio cost is not available.")
            ),
        },
        "retell": {
            "status": retell_label,
            "status_class": retell_class,
            "usage": f"{retell_count} {'AI call' if retell_count == 1 else 'AI calls'}",
            "usage_source": "Based on Retell AI calls recorded in RSF.",
            "cost": None,
            "cost_currency": "",
            "cost_source": "Retell AI billing is not connected to this dashboard.",
        },
    }

    rows = []
    totals_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    cost_available_count = 0
    active_count = 0
    needs_setup_count = 0

    for slug, name in SERVICE_DEFINITIONS:
        item = service_runtime[slug]
        cost = item["cost"]
        currency = item["cost_currency"]

        if cost is not None:
            totals_by_currency[currency or ""] += cost
            cost_available_count += 1
        if item["status_class"] == "connected":
            active_count += 1
        else:
            needs_setup_count += 1

        rows.append({
            "slug": slug,
            "name": name,
            **item,
            "cost_text": _money_text(cost, currency),
        })

    if not totals_by_currency:
        known_cost_text = "Not available"
    elif len(totals_by_currency) == 1:
        currency, amount = next(iter(totals_by_currency.items()))
        known_cost_text = _money_text(amount, currency)
    else:
        known_cost_text = "Multiple currencies"

    service_count = len(SERVICE_DEFINITIONS)
    return {
        "rows": rows,
        "month_label": datetime.now(timezone.utc).strftime("%B %Y"),
        "summary": {
            "known_cost_text": known_cost_text,
            "cost_available_count": cost_available_count,
            "cost_missing_count": service_count - cost_available_count,
            "service_count": service_count,
            "active_count": active_count,
            "needs_setup_count": needs_setup_count,
        },
    }
