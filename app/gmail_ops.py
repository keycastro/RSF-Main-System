from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, session

from .db import get_db
from .services import normalize_email, utcnow_iso


GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

_token_lock = threading.Lock()
_token_cache = {"access_token": "", "expires_at": 0.0}


class GmailAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _fernet() -> Fernet:
    secret = (current_app.config.get("CREDENTIAL_VAULT_KEY") or current_app.config.get("SECRET_KEY") or "").strip()
    if not secret:
        raise RuntimeError("RSF credential vault key is not configured.")
    material = hashlib.sha256(("rsf-gmail-oauth-v1:" + secret).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def _encrypt_secret(value: str) -> str:
    if not value:
        raise ValueError("Gmail refresh token is missing.")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt((value or "").encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("Stored Gmail authorization could not be decrypted.") from exc


def oauth_client_configured() -> bool:
    return bool(
        current_app.config.get("GMAIL_OAUTH_CLIENT_ID")
        and current_app.config.get("GMAIL_OAUTH_CLIENT_SECRET")
        and current_app.config.get("GMAIL_OAUTH_REDIRECT_URI")
    )


def _credential_row():
    try:
        return get_db().execute(
            "SELECT * FROM gmail_oauth_credentials WHERE id=1"
        ).fetchone()
    except Exception:
        return None


def connected_email() -> str:
    row = _credential_row()
    return normalize_email(row["email_address"]) if row else ""


def gmail_connected() -> bool:
    if not oauth_client_configured():
        return False
    row = _credential_row()
    if not row or not row["encrypted_refresh_token"]:
        return False
    configured = normalize_email(current_app.config.get("RSF_EMAIL_ADDRESS", ""))
    actual = normalize_email(row["email_address"])
    return bool(actual and (not configured or configured == actual))


def connection_status() -> dict:
    row = _credential_row()
    configured_sender = normalize_email(current_app.config.get("RSF_EMAIL_ADDRESS", ""))
    actual = normalize_email(row["email_address"]) if row else ""
    connected = bool(
        oauth_client_configured()
        and row
        and row["encrypted_refresh_token"]
        and actual
        and (not configured_sender or configured_sender == actual)
    )
    return {
        "oauth_configured": oauth_client_configured(),
        "connected": connected,
        "email": actual,
        "configured_sender": configured_sender,
        "connected_at": row["connected_at"] if row else "",
        "updated_at": row["updated_at"] if row else "",
    }


def build_authorization_url(redirect_uri: str) -> str:
    if not oauth_client_configured():
        raise RuntimeError("Gmail OAuth client is not configured.")
    state = base64.urlsafe_b64encode(__import__("secrets").token_bytes(32)).decode("ascii").rstrip("=")
    session["gmail_oauth_state"] = state
    params = {
        "client_id": current_app.config["GMAIL_OAUTH_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    configured_sender = normalize_email(current_app.config.get("RSF_EMAIL_ADDRESS", ""))
    if configured_sender:
        params["login_hint"] = configured_sender
    return GOOGLE_AUTH_URL + "?" + urlencode(params)


def validate_oauth_state(received_state: str) -> None:
    expected = session.pop("gmail_oauth_state", "")
    if not expected or not received_state or not __import__("hmac").compare_digest(expected, received_state):
        raise RuntimeError("Gmail authorization session expired or is invalid. Try connecting Gmail again.")


def _decode_json_response(response) -> dict:
    raw = response.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _google_error(exc: HTTPError, fallback: str) -> GmailAPIError:
    message = fallback
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict) and err.get("message"):
                message = str(err["message"])
            elif isinstance(err, str):
                message = err
    except Exception:
        pass
    return GmailAPIError(message, getattr(exc, "code", None))


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
        raise GmailAPIError("Could not reach Google Gmail services.") from exc


def exchange_authorization_code(code: str, redirect_uri: str) -> dict:
    if not code:
        raise RuntimeError("Google did not return an authorization code.")
    payload = _form_post(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": current_app.config["GMAIL_OAUTH_CLIENT_ID"],
            "client_secret": current_app.config["GMAIL_OAUTH_CLIENT_SECRET"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if not payload.get("access_token"):
        raise RuntimeError("Google did not return a Gmail access token.")
    return payload


def _api_request(method: str, path: str, *, access_token: str, payload: dict | None = None, query: dict | None = None) -> dict:
    url = GMAIL_API_BASE + path
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
        raise _google_error(exc, "Gmail API request failed.") from exc
    except (URLError, TimeoutError) as exc:
        raise GmailAPIError("Could not reach the Gmail API.") from exc


def gmail_profile(access_token: str | None = None) -> dict:
    token = access_token or access_token_for_api()
    return _api_request("GET", "/profile", access_token=token)


def store_authorization(*, email_address: str, refresh_token: str, scope: str, history_id: str = "") -> None:
    email_address = normalize_email(email_address)
    if not email_address:
        raise RuntimeError("Google Gmail account email could not be verified.")
    configured = normalize_email(current_app.config.get("RSF_EMAIL_ADDRESS", ""))
    if configured and configured != email_address:
        raise RuntimeError(f"Connect the approved RSF sender account: {configured}.")
    db = get_db()
    now = utcnow_iso()
    db.execute(
        """INSERT INTO gmail_oauth_credentials
           (id,email_address,encrypted_refresh_token,scope,history_id,connected_at,updated_at)
           VALUES (1,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             email_address=excluded.email_address,
             encrypted_refresh_token=excluded.encrypted_refresh_token,
             scope=excluded.scope,
             history_id=excluded.history_id,
             connected_at=excluded.connected_at,
             updated_at=excluded.updated_at""",
        (email_address, _encrypt_secret(refresh_token), scope or GMAIL_SCOPE, str(history_id or ""), now, now),
    )
    db.commit()


def complete_authorization(code: str, redirect_uri: str) -> str:
    payload = exchange_authorization_code(code, redirect_uri)
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        existing = _credential_row()
        if existing and existing["encrypted_refresh_token"]:
            refresh_token = _decrypt_secret(existing["encrypted_refresh_token"])
        else:
            raise RuntimeError("Google did not return an offline refresh token. Reconnect Gmail and approve access.")
    profile = gmail_profile(str(payload["access_token"]))
    email_address = normalize_email(profile.get("emailAddress", ""))
    store_authorization(
        email_address=email_address,
        refresh_token=refresh_token,
        scope=str(payload.get("scope") or GMAIL_SCOPE),
        history_id=str(profile.get("historyId") or ""),
    )
    expires_in = int(payload.get("expires_in") or 3600)
    with _token_lock:
        _token_cache["access_token"] = str(payload["access_token"])
        _token_cache["expires_at"] = time.time() + max(60, expires_in - 60)
    return email_address


def access_token_for_api() -> str:
    with _token_lock:
        if _token_cache["access_token"] and float(_token_cache["expires_at"]) > time.time():
            return str(_token_cache["access_token"])
    if not oauth_client_configured():
        raise RuntimeError("Gmail OAuth client is not configured.")
    row = _credential_row()
    if not row or not row["encrypted_refresh_token"]:
        raise RuntimeError("Gmail is not connected to RSF yet.")
    refresh_token = _decrypt_secret(row["encrypted_refresh_token"])
    payload = _form_post(
        GOOGLE_TOKEN_URL,
        {
            "client_id": current_app.config["GMAIL_OAUTH_CLIENT_ID"],
            "client_secret": current_app.config["GMAIL_OAUTH_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise RuntimeError("Google could not refresh the Gmail connection. Reconnect Gmail in Settings.")
    expires_in = int(payload.get("expires_in") or 3600)
    with _token_lock:
        _token_cache["access_token"] = access_token
        _token_cache["expires_at"] = time.time() + max(60, expires_in - 60)
    return access_token


def send_raw_message(raw_message: bytes) -> dict:
    encoded = base64.urlsafe_b64encode(raw_message).decode("ascii").rstrip("=")
    return _api_request(
        "POST",
        "/messages/send",
        access_token=access_token_for_api(),
        payload={"raw": encoded},
    )


def _history_row():
    return _credential_row()


def set_history_id(history_id: str) -> None:
    if not history_id:
        return
    db = get_db()
    db.execute(
        "UPDATE gmail_oauth_credentials SET history_id=?,updated_at=? WHERE id=1",
        (str(history_id), utcnow_iso()),
    )
    db.commit()


def reset_history_baseline() -> str:
    profile = gmail_profile()
    history_id = str(profile.get("historyId") or "")
    set_history_id(history_id)
    return history_id


def history_message_ids(limit: int = 100) -> tuple[list[str], str]:
    row = _history_row()
    if not row:
        raise RuntimeError("Gmail is not connected to RSF yet.")
    start_history_id = str(row["history_id"] or "")
    if not start_history_id:
        return [], reset_history_baseline()

    token = access_token_for_api()
    ids: list[str] = []
    latest_history_id = start_history_id
    page_token = ""
    remaining = max(1, min(int(limit), 500))
    while remaining > 0:
        query = {
            "startHistoryId": start_history_id,
            "historyTypes": "messageAdded",
            "maxResults": min(100, remaining),
        }
        if page_token:
            query["pageToken"] = page_token
        try:
            payload = _api_request("GET", "/history", access_token=token, query=query)
        except GmailAPIError as exc:
            if exc.status_code == 404:
                return [], reset_history_baseline()
            raise
        latest_history_id = str(payload.get("historyId") or latest_history_id)
        for history in payload.get("history") or []:
            for added in history.get("messagesAdded") or []:
                message = added.get("message") or {}
                message_id = str(message.get("id") or "")
                if message_id and message_id not in ids:
                    ids.append(message_id)
                    remaining -= 1
                    if remaining <= 0:
                        break
            if remaining <= 0:
                break
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token or remaining <= 0:
            break
    return ids, latest_history_id


def raw_message(message_id: str) -> bytes:
    payload = _api_request(
        "GET",
        f"/messages/{message_id}",
        access_token=access_token_for_api(),
        query={"format": "raw"},
    )
    raw = str(payload.get("raw") or "")
    if not raw:
        raise RuntimeError("Gmail returned an empty message.")
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def verify_connection() -> dict:
    if not gmail_connected():
        raise RuntimeError("Gmail is not fully connected to RSF.")
    profile = gmail_profile()
    expected = connected_email()
    actual = normalize_email(profile.get("emailAddress", ""))
    if not actual or actual != expected:
        raise RuntimeError("Connected Gmail account does not match the RSF email identity.")
    return profile
