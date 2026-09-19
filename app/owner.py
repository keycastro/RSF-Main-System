from __future__ import annotations

import hmac
import secrets
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .inquiries import ALLOWED_STATUSES, counts, get_inquiry, list_inquiries, update_status
from .system_templates import split_subscription_action

owner = Blueprint("owner", __name__)

_OWNER_SESSION_KEY = "key_castro_owner_authenticated"
_OWNER_CSRF_KEY = "key_castro_owner_csrf"
_OWNER_TICKET_SALT = "key-castro-owner-inbox-access-v1"
_OWNER_TICKET_MAX_AGE = 90


def _api_allowed() -> bool:
    expected = (current_app.config.get("OWNER_INBOX_TOKEN") or "").strip()
    header = request.headers.get("Authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _api_guard() -> None:
    if not _api_allowed():
        abort(404)


def _owner_guard() -> None:
    if not session.get(_OWNER_SESSION_KEY):
        # Intentionally look like a missing page. There is no public owner login page.
        abort(404)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.secret_key, salt=_OWNER_TICKET_SALT)


def _owner_csrf() -> str:
    token = session.get(_OWNER_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_OWNER_CSRF_KEY] = token
    return token


def _verify_owner_csrf() -> None:
    expected = session.get(_OWNER_CSRF_KEY, "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400)


def _format_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        timezone_name = current_app.config.get("OWNER_TIMEZONE", "Asia/Manila")
        try:
            parsed = parsed.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            parsed = parsed.astimezone()
        return parsed.strftime("%b %d, %Y · %I:%M %p")
    except (TypeError, ValueError):
        return value


def _prepare_item(item: dict) -> dict:
    prepared = dict(item)
    prepared["date_label"] = _format_date(prepared.get("created_at"))
    message = prepared.get("message") or ""
    prepared["preview"] = (message[:180] + "…") if len(message) > 180 else message
    request_label, plan_label = split_subscription_action(prepared.get("source_action") or "")
    prepared["request_label"] = request_label
    prepared["plan_label"] = plan_label
    prepared["reply_url"] = "mailto:" + urllib.parse.quote(prepared.get("email", ""), safe="@+._-") + "?subject=" + urllib.parse.quote(
        "Re: Your project inquiry to Key Castro"
    )
    return prepared


@owner.get("/__owner_api/health")
def owner_api_health():
    _api_guard()
    return jsonify(status="ok", counts=counts())


@owner.get("/__owner_api/inquiries")
def owner_api_inquiries():
    _api_guard()
    status = request.args.get("status", "").strip().lower() or None
    if status and status not in ALLOWED_STATUSES:
        abort(400)
    return jsonify(items=list_inquiries(status=status), counts=counts())


@owner.get("/__owner_api/inquiries/<int:inquiry_id>")
def owner_api_inquiry_detail(inquiry_id: int):
    _api_guard()
    item = get_inquiry(inquiry_id)
    if item is None:
        abort(404)
    if item.get("status") == "new":
        item = update_status(inquiry_id, "read") or item
    return jsonify(item=item)


@owner.post("/__owner_api/inquiries/<int:inquiry_id>/status")
def owner_api_inquiry_status(inquiry_id: int):
    _api_guard()
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).strip().lower()
    if status not in ALLOWED_STATUSES:
        return jsonify(error="invalid_status"), 400
    item = update_status(inquiry_id, status)
    if item is None:
        abort(404)
    return jsonify(item=item)


@owner.post("/__owner_api/session-ticket")
def owner_session_ticket():
    """Exchange the locally stored owner token for a short-lived browser access URL."""
    _api_guard()
    ticket = _serializer().dumps({"purpose": "owner-inbox"})
    return jsonify(
        status="ok",
        url=url_for("owner.owner_access", ticket=ticket, _external=True),
        expires_in_seconds=_OWNER_TICKET_MAX_AGE,
    )


@owner.get("/__owner_access/<ticket>")
def owner_access(ticket: str):
    try:
        payload = _serializer().loads(ticket, max_age=_OWNER_TICKET_MAX_AGE)
    except (SignatureExpired, BadSignature):
        abort(404)
    if payload.get("purpose") != "owner-inbox":
        abort(404)

    session.clear()
    session.permanent = True
    session[_OWNER_SESSION_KEY] = True
    session[_OWNER_CSRF_KEY] = secrets.token_urlsafe(32)
    return redirect(url_for("owner.owner_inbox"))


@owner.get("/owner/inbox")
def owner_inbox():
    _owner_guard()
    status = request.args.get("status", "").strip().lower() or None
    if status and status not in ALLOWED_STATUSES:
        abort(400)

    items = [_prepare_item(item) for item in list_inquiries(status=status)]
    return render_template(
        "owner/inbox.html",
        title="Private Inbox",
        items=items,
        counts=counts(),
        current_status=status or "",
        csrf_token=_owner_csrf(),
    )


@owner.get("/owner/inbox/<int:inquiry_id>")
def owner_inquiry(inquiry_id: int):
    _owner_guard()
    item = get_inquiry(inquiry_id)
    if item is None:
        abort(404)
    if item.get("status") == "new":
        item = update_status(inquiry_id, "read") or item
    return render_template(
        "owner/inquiry.html",
        title="Inquiry",
        item=_prepare_item(item),
        csrf_token=_owner_csrf(),
    )


@owner.post("/owner/inbox/<int:inquiry_id>/status")
def owner_inquiry_status(inquiry_id: int):
    _owner_guard()
    _verify_owner_csrf()
    status = request.form.get("status", "").strip().lower()
    if status not in ALLOWED_STATUSES:
        abort(400)
    if update_status(inquiry_id, status) is None:
        abort(404)
    return redirect(url_for("owner.owner_inquiry", inquiry_id=inquiry_id))


@owner.post("/owner/logout")
def owner_logout():
    _owner_guard()
    _verify_owner_csrf()
    session.clear()
    return redirect(url_for("site.home"))
