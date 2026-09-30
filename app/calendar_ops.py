from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, session

from .db import get_db
from .services import normalize_email, utcnow_iso


CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

_token_lock = threading.Lock()
_token_cache = {"access_token": "", "expires_at": 0.0}

PHILIPPINES_TIMEZONE = "Asia/Manila"


def timezone_options() -> list[str]:
    return sorted(
        zone
        for zone in available_timezones()
        if "/" in zone and not zone.startswith(("Etc/", "posix/", "right/"))
    )


def validate_demo_timezone(value: str) -> str:
    timezone_name = (value or "").strip()[:120]
    if not timezone_name:
        return ""
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Select a valid client time zone.") from exc
    return timezone_name


def _friendly_demo_time(value: datetime) -> str:
    month = value.strftime("%b")
    day = str(value.day)
    hour = value.strftime("%I").lstrip("0") or "0"
    minute = value.strftime("%M")
    ampm = value.strftime("%p")
    return f"{month} {day} · {hour}:{minute} {ampm}"


def demo_time_display(demo_date: str, demo_time: str, demo_timezone: str) -> dict[str, str]:
    demo_date = (demo_date or "").strip()
    demo_time = (demo_time or "").strip()
    demo_timezone = (demo_timezone or "").strip()
    if not demo_date or not demo_time:
        return {"client": "Set demo date and time", "philippines": "—"}
    try:
        local_naive = datetime.fromisoformat(f"{demo_date}T{demo_time}:00")
    except ValueError:
        return {"client": "Invalid demo date or time", "philippines": "—"}

    if not demo_timezone:
        return {
            "client": f"{_friendly_demo_time(local_naive)} · Select client time zone",
            "philippines": "Select client time zone",
        }
    try:
        client_zone = ZoneInfo(demo_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return {
            "client": f"{_friendly_demo_time(local_naive)} · Invalid time zone",
            "philippines": "Invalid client time zone",
        }

    client_time = local_naive.replace(tzinfo=client_zone)
    philippines_time = client_time.astimezone(ZoneInfo(PHILIPPINES_TIMEZONE))
    return {
        "client": f"{_friendly_demo_time(client_time)} · {demo_timezone}",
        "philippines": _friendly_demo_time(philippines_time),
    }


class CalendarAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _fernet() -> Fernet:
    secret = (current_app.config.get("CREDENTIAL_VAULT_KEY") or current_app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("RSF credential vault key is not configured.")
    material = hashlib.sha256(("rsf-google-calendar-oauth-v1:" + secret).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def _encrypt_secret(value: str) -> str:
    if not value:
        raise ValueError("Google Calendar refresh token is missing.")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt((value or "").encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Stored Google Calendar authorization could not be decrypted.") from exc


def _client_id() -> str:
    return (
        current_app.config.get("GOOGLE_CALENDAR_OAUTH_CLIENT_ID")
        or current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
        or current_app.config.get("GMAIL_OAUTH_CLIENT_ID")
        or ""
    ).strip()


def _client_secret() -> str:
    return (
        current_app.config.get("GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET")
        or current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
        or current_app.config.get("GMAIL_OAUTH_CLIENT_SECRET")
        or ""
    ).strip()


def oauth_client_configured() -> bool:
    return bool(_client_id() and _client_secret() and current_app.config.get("GOOGLE_CALENDAR_OAUTH_REDIRECT_URI"))


def _credential_row():
    try:
        return get_db().execute("SELECT * FROM google_calendar_oauth_credentials WHERE id=1").fetchone()
    except Exception:
        return None


def calendar_connected() -> bool:
    row = _credential_row()
    return bool(oauth_client_configured() and row and row["encrypted_refresh_token"])


def connection_status() -> dict:
    row = _credential_row()
    return {
        "oauth_configured": oauth_client_configured(),
        "connected": calendar_connected(),
        "calendar_id": (row["calendar_id"] if row else "") or "primary",
        "connected_at": row["connected_at"] if row else "",
        "updated_at": row["updated_at"] if row else "",
        "timezone": current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Manila"),
    }


def build_authorization_url(redirect_uri: str) -> str:
    if not oauth_client_configured():
        raise RuntimeError("Google Calendar OAuth client is not configured.")
    state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
    session["google_calendar_oauth_state"] = state
    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return GOOGLE_AUTH_URL + "?" + urlencode(params)


def validate_oauth_state(received_state: str) -> None:
    import hmac
    expected = session.pop("google_calendar_oauth_state", "")
    if not expected or not received_state or not hmac.compare_digest(expected, received_state):
        raise RuntimeError("Google Calendar authorization session expired or is invalid. Try connecting again.")


def _decode_json_response(response) -> dict:
    raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def _google_error(exc: HTTPError, fallback: str) -> CalendarAPIError:
    message = fallback
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and error.get("message"):
            message = str(error["message"])
        elif isinstance(error, str):
            message = error
    except Exception:
        pass
    return CalendarAPIError(message, getattr(exc, "code", None))


def _form_post(url: str, values: dict) -> dict:
    request = Request(
        url,
        data=urlencode(values).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return _decode_json_response(response)
    except HTTPError as exc:
        raise _google_error(exc, "Google authorization request failed.") from exc
    except (URLError, TimeoutError) as exc:
        raise CalendarAPIError("Could not reach Google services.") from exc


def _api_request(method: str, path: str, *, access_token: str, payload: dict | None = None, query: dict | None = None) -> dict:
    url = CALENDAR_API_BASE + path
    if query:
        url += "?" + urlencode(query, doseq=True)
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            return _decode_json_response(response)
    except HTTPError as exc:
        raise _google_error(exc, "Google Calendar API request failed.") from exc
    except (URLError, TimeoutError) as exc:
        raise CalendarAPIError("Could not reach Google Calendar.") from exc


def store_authorization(refresh_token: str, scope: str) -> None:
    db = get_db()
    now = utcnow_iso()
    db.execute(
        """INSERT INTO google_calendar_oauth_credentials
           (id,calendar_id,encrypted_refresh_token,scope,connected_at,updated_at)
           VALUES (1,'primary',?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             calendar_id=excluded.calendar_id,
             encrypted_refresh_token=excluded.encrypted_refresh_token,
             scope=excluded.scope,
             connected_at=excluded.connected_at,
             updated_at=excluded.updated_at""",
        (_encrypt_secret(refresh_token), scope or CALENDAR_SCOPE, now, now),
    )
    db.commit()


def complete_authorization(code: str, redirect_uri: str) -> None:
    if not code:
        raise RuntimeError("Google did not return an authorization code.")
    payload = _form_post(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if not payload.get("access_token"):
        raise RuntimeError("Google did not return a Calendar access token.")
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        row = _credential_row()
        if row and row["encrypted_refresh_token"]:
            refresh_token = _decrypt_secret(row["encrypted_refresh_token"])
        else:
            raise RuntimeError("Google did not return an offline refresh token. Reconnect and approve Calendar access.")
    store_authorization(refresh_token, str(payload.get("scope") or CALENDAR_SCOPE))
    expires_in = int(payload.get("expires_in") or 3600)
    with _token_lock:
        _token_cache["access_token"] = str(payload["access_token"])
        _token_cache["expires_at"] = time.time() + max(60, expires_in - 60)


def access_token_for_api() -> str:
    with _token_lock:
        if _token_cache["access_token"] and float(_token_cache["expires_at"]) > time.time():
            return str(_token_cache["access_token"])
    if not oauth_client_configured():
        raise RuntimeError("Google Calendar OAuth client is not configured.")
    row = _credential_row()
    if not row or not row["encrypted_refresh_token"]:
        raise RuntimeError("Google Calendar is not connected to RSF yet.")
    payload = _form_post(
        GOOGLE_TOKEN_URL,
        {
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": _decrypt_secret(row["encrypted_refresh_token"]),
            "grant_type": "refresh_token",
        },
    )
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("Google could not refresh the Calendar connection. Reconnect Google Calendar in Settings.")
    expires_in = int(payload.get("expires_in") or 3600)
    with _token_lock:
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = time.time() + max(60, expires_in - 60)
    return token


def verify_connection() -> dict:
    if not calendar_connected():
        raise RuntimeError("Google Calendar is not fully connected to RSF.")
    return _api_request(
        "GET",
        "/calendars/primary/events",
        access_token=access_token_for_api(),
        query={"maxResults": 1, "singleEvents": "true"},
    )


def _meeting_url(event: dict) -> str:
    direct = str(event.get("hangoutLink") or "").strip()
    if direct:
        return direct
    conference = event.get("conferenceData") or {}
    for entry in conference.get("entryPoints") or []:
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return str(entry["uri"])
    return ""


def _event_payload(*, client_name: str, client_email: str, demo_date: str, demo_time: str, demo_timezone: str) -> dict:
    timezone_name = validate_demo_timezone(demo_timezone)
    if not timezone_name:
        raise RuntimeError("Client time zone is required before scheduling the demo.")
    duration = int(current_app.config.get("GOOGLE_CALENDAR_DEMO_DURATION_MINUTES", 60))
    tz = ZoneInfo(timezone_name)
    start_local = datetime.fromisoformat(f"{demo_date}T{demo_time}:00").replace(tzinfo=tz)
    end_local = start_local + timedelta(minutes=duration)
    payload = {
        "summary": f"RSF Demo — {client_name or 'Client'}",
        "description": "Client demo scheduled from RSF Workspace.",
        "start": {"dateTime": start_local.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end_local.isoformat(), "timeZone": timezone_name},
    }
    attendee = normalize_email(client_email)
    if attendee and "@" in attendee:
        payload["attendees"] = [{"email": attendee}]
    return payload


def create_or_update_deal_meeting(
    *,
    event_id: str,
    client_name: str,
    client_email: str,
    demo_date: str,
    demo_time: str,
    demo_timezone: str,
) -> dict:
    if not calendar_connected():
        raise RuntimeError("Google Calendar is not connected to RSF yet.")
    payload = _event_payload(
        client_name=client_name,
        client_email=client_email,
        demo_date=demo_date,
        demo_time=demo_time,
        demo_timezone=demo_timezone,
    )
    token = access_token_for_api()
    encoded_calendar = quote("primary", safe="")
    result = None
    if event_id:
        try:
            result = _api_request(
                "PATCH",
                f"/calendars/{encoded_calendar}/events/{quote(event_id, safe='')}",
                access_token=token,
                payload=payload,
                query={"conferenceDataVersion": 1, "sendUpdates": "all"},
            )
        except CalendarAPIError as exc:
            if exc.status_code != 404:
                raise
            event_id = ""

    if not event_id:
        payload["conferenceData"] = {
            "createRequest": {
                "requestId": secrets.token_urlsafe(18),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        result = _api_request(
            "POST",
            f"/calendars/{encoded_calendar}/events",
            access_token=token,
            payload=payload,
            query={"conferenceDataVersion": 1, "sendUpdates": "all"},
        )

    result = result or {}
    final_event_id = str(result.get("id") or event_id or "")
    meet_url = _meeting_url(result)
    if final_event_id and not meet_url:
        for _ in range(4):
            time.sleep(0.4)
            result = _api_request(
                "GET",
                f"/calendars/{encoded_calendar}/events/{quote(final_event_id, safe='')}",
                access_token=token,
            )
            meet_url = _meeting_url(result)
            if meet_url:
                break
    return {
        "event_id": final_event_id,
        "html_link": str(result.get("htmlLink") or ""),
        "meet_url": meet_url,
    }
