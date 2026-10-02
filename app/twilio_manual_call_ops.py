from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from flask import current_app


def normalize_e164(value: str | None) -> str:
    raw = (value or "").strip()
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    compact = "".join(ch for ch in raw if ch.isdigit())
    if raw.startswith("+"):
        return f"+{compact}" if 8 <= len(compact) <= 15 else ""
    if len(compact) == 11 and compact.startswith("09"):
        return "+63" + compact[1:]
    if len(compact) == 12 and compact.startswith("639"):
        return "+" + compact
    return ""


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


def _twilio_post(path: str, payload: list[tuple[str, str]], fallback: str, timeout: int = 25) -> dict:
    sid = (current_app.config.get("TWILIO_ACCOUNT_SID") or "").strip()
    token = (current_app.config.get("TWILIO_AUTH_TOKEN") or "").strip()
    if not sid or not token:
        raise RuntimeError("Manual Call service is not connected yet.")
    req = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path.lstrip('/')}",
        data=urlencode(payload).encode("utf-8"),
        headers={
            "Authorization": _basic_auth(sid, token),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_message(exc, fallback)) from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(fallback) from exc


def create_manual_bridge_call(
    *,
    twiml_url: str,
    status_callback_url: str,
    recording_status_callback_url: str,
) -> str:
    if not manual_call_configured():
        raise RuntimeError("Manual Call service is not connected yet.")
    payload = [
        ("To", current_app.config["TWILIO_AGENT_NUMBER"]),
        ("From", current_app.config["TWILIO_FROM_NUMBER"]),
        ("Url", twiml_url),
        ("Method", "POST"),
        ("StatusCallback", status_callback_url),
        ("StatusCallbackMethod", "POST"),
        ("StatusCallbackEvent", "initiated"),
        ("StatusCallbackEvent", "ringing"),
        ("StatusCallbackEvent", "answered"),
        ("StatusCallbackEvent", "completed"),
        ("Record", "true"),
        ("RecordingChannels", "dual"),
        ("RecordingTrack", "both"),
        ("RecordingStatusCallback", recording_status_callback_url),
        ("RecordingStatusCallbackMethod", "POST"),
        ("RecordingStatusCallbackEvent", "completed absent"),
    ]
    data = _twilio_post("Calls.json", payload, "Twilio could not start the manual call.")
    call_sid = str(data.get("sid") or "").strip()
    if not call_sid:
        raise RuntimeError("Twilio did not return a Call SID.")
    return call_sid


def create_manual_client_call(*, to_number: str, twiml_url: str, status_callback_url: str) -> str:
    if not manual_call_configured():
        raise RuntimeError("Manual Call service is not connected yet.")
    destination = normalize_e164(to_number)
    if not destination:
        raise ValueError("Contact Number must use a valid international phone format.")
    payload = [
        ("To", destination),
        ("From", current_app.config["TWILIO_FROM_NUMBER"]),
        ("Url", twiml_url),
        ("Method", "POST"),
        ("StatusCallback", status_callback_url),
        ("StatusCallbackMethod", "POST"),
        ("StatusCallbackEvent", "initiated"),
        ("StatusCallbackEvent", "ringing"),
        ("StatusCallbackEvent", "answered"),
        ("StatusCallbackEvent", "completed"),
    ]
    data = _twilio_post("Calls.json", payload, "Twilio could not connect the client call.")
    call_sid = str(data.get("sid") or "").strip()
    if not call_sid:
        raise RuntimeError("Twilio did not return a client Call SID.")
    return call_sid


def update_conference_participant(
    *,
    conference_sid: str,
    call_sid: str,
    muted: bool | None = None,
    hold: bool | None = None,
) -> dict:
    if not conference_sid or not call_sid:
        raise RuntimeError("The live call control is not ready yet.")
    payload: list[tuple[str, str]] = []
    if muted is not None:
        payload.append(("Muted", "true" if muted else "false"))
    if hold is not None:
        payload.append(("Hold", "true" if hold else "false"))
    if not payload:
        raise ValueError("No Manual Call control change was requested.")
    return _twilio_post(
        f"Conferences/{quote(conference_sid, safe='')}/Participants/{quote(call_sid, safe='')}.json",
        payload,
        "Twilio could not update the live call control.",
    )


def end_manual_call(*, conference_sid: str, agent_call_sid: str, client_call_sid: str = "") -> None:
    if conference_sid:
        _twilio_post(
            f"Conferences/{quote(conference_sid, safe='')}.json",
            [("Status", "completed")],
            "Twilio could not end the Manual Call.",
        )
        return
    errors: list[Exception] = []
    ended = False
    seen: set[str] = set()
    for call_sid in (client_call_sid, agent_call_sid):
        if not call_sid or call_sid in seen:
            continue
        seen.add(call_sid)
        try:
            _twilio_post(
                f"Calls/{quote(call_sid, safe='')}.json",
                [("Status", "completed")],
                "Twilio could not end the Manual Call.",
            )
            ended = True
        except RuntimeError as exc:
            errors.append(exc)
    if not ended and errors:
        raise errors[0]



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
