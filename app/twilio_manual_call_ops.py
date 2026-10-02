from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app


def normalize_e164(value: str | None) -> str:
    raw = (value or "").strip()
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if not raw.startswith("+"):
        return ""
    digits = "".join(ch for ch in raw[1:] if ch.isdigit())
    return f"+{digits}" if 8 <= len(digits) <= 15 else ""


def manual_call_configured() -> bool:
    return bool(
        current_app.config.get("TWILIO_ACCOUNT_SID")
        and current_app.config.get("TWILIO_AUTH_TOKEN")
        and current_app.config.get("TWILIO_FROM_NUMBER")
        and current_app.config.get("TWILIO_AGENT_NUMBER")
    )


def batch_transcription_configured() -> bool:
    return bool(
        current_app.config.get("TWILIO_API_KEY")
        and current_app.config.get("TWILIO_API_SECRET")
        and current_app.config.get("TWILIO_BATCH_TRANSCRIPTION_CONFIGURATION_ID")
        and current_app.config.get("TWILIO_TRANSCRIPTION_WEBHOOK_SECRET")
    )


def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _http_error_message(exc: HTTPError, fallback: str) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        message = str(data.get("message") or data.get("detail") or "").strip()
        if message:
            return message[:1200]
    except Exception:
        pass
    return fallback


def create_manual_bridge_call(*, twiml_url: str, status_callback_url: str) -> str:
    if not manual_call_configured():
        raise RuntimeError("Manual Call service is not connected yet.")
    sid = current_app.config["TWILIO_ACCOUNT_SID"]
    token = current_app.config["TWILIO_AUTH_TOKEN"]
    payload = urlencode({
        "To": current_app.config["TWILIO_AGENT_NUMBER"],
        "From": current_app.config["TWILIO_FROM_NUMBER"],
        "Url": twiml_url,
        "Method": "POST",
        "StatusCallback": status_callback_url,
        "StatusCallbackMethod": "POST",
        "StatusCallbackEvent": "initiated ringing answered completed",
    }).encode("utf-8")
    req = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
        data=payload,
        headers={
            "Authorization": _basic_auth(sid, token),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc, "Twilio could not start the manual call.")) from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Twilio could not be reached to start the manual call.") from exc
    call_sid = str(data.get("sid") or "").strip()
    if not call_sid:
        raise RuntimeError("Twilio did not return a Call SID.")
    return call_sid


def download_recording(recording_url: str) -> tuple[bytes, str]:
    sid = (current_app.config.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (current_app.config.get("TWILIO_AUTH_TOKEN") or "").strip()
    if not sid or not token:
        raise RuntimeError("Twilio recording credentials are not configured.")
    url = (recording_url or "").strip()
    if not url:
        raise ValueError("Recording URL is missing.")
    if not url.lower().endswith(".mp3"):
        url += ".mp3"
    req = Request(
        url,
        headers={"Authorization": _basic_auth(sid, token), "Accept": "audio/mpeg"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=45) as response:
            data = response.read()
            mime = response.headers.get_content_type() or "audio/mpeg"
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc, "Twilio recording download failed.")) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Twilio recording could not be downloaded.") from exc
    return data, mime


def create_batch_transcription(recording_sid: str) -> str:
    if not batch_transcription_configured():
        return ""
    api_key = current_app.config["TWILIO_API_KEY"]
    api_secret = current_app.config["TWILIO_API_SECRET"]
    config_id = current_app.config["TWILIO_BATCH_TRANSCRIPTION_CONFIGURATION_ID"]
    payload = json.dumps({
        "transcriptionConfigurationId": config_id,
        "sourceId": recording_sid,
    }).encode("utf-8")
    req = Request(
        "https://voice.twilio.com/v3/Transcriptions",
        data=payload,
        headers={
            "Authorization": _basic_auth(api_key, api_secret),
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc, "Twilio transcription could not be started.")) from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Twilio transcription service could not be reached.") from exc
    transcription = data.get("transcription") or {}
    return str(transcription.get("id") or data.get("operationId") or "").strip()


def validate_form_webhook(url: str, form_values: dict[str, list[str]], signature: str | None) -> bool:
    token = (current_app.config.get("TWILIO_AUTH_TOKEN") or "").strip()
    supplied = (signature or "").strip()
    if not token or not supplied:
        return False
    message = url
    for key in sorted(form_values):
        values = form_values.get(key) or [""]
        for value in sorted(str(item) for item in values):
            message += f"{key}{value}"
    digest = hmac.new(token.encode("utf-8"), message.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, supplied)
