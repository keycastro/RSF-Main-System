from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app


def normalize_whatsapp_number(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not (8 <= len(digits) <= 15):
        return ""
    return f"+{digits}"


def whatsapp_messaging_configured() -> bool:
    return bool(
        current_app.config.get("WHATSAPP_GRAPH_API_VERSION")
        and current_app.config.get("WHATSAPP_ACCESS_TOKEN")
        and current_app.config.get("WHATSAPP_PHONE_NUMBER_ID")
    )


def whatsapp_webhook_verify_configured() -> bool:
    return bool(current_app.config.get("WHATSAPP_VERIFY_TOKEN"))


def whatsapp_webhook_signature_configured() -> bool:
    return bool(current_app.config.get("WHATSAPP_APP_SECRET"))


def _graph_base() -> str:
    version = (current_app.config.get("WHATSAPP_GRAPH_API_VERSION") or "").strip()
    if not version:
        raise RuntimeError("WhatsApp Graph API version is not configured.")
    return f"https://graph.facebook.com/{version}"


def _access_token() -> str:
    token = (current_app.config.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("WhatsApp access token is not configured.")
    return token


def _phone_number_id() -> str:
    value = (current_app.config.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    if not value:
        raise RuntimeError("WhatsApp phone number ID is not configured.")
    return value


def _decode_http_error(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        message = ((payload.get("error") or {}).get("message") or "").strip()
        if message:
            return message[:1000]
    except Exception:
        pass
    return f"WhatsApp API request failed with HTTP {exc.code}."


def _json_request(url: str, *, method: str = "GET", payload: dict | None = None, bearer: bool = True) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if bearer:
        headers["Authorization"] = f"Bearer {_access_token()}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=25) as response:
            raw = response.read()
    except HTTPError as exc:
        raise RuntimeError(_decode_http_error(exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("WhatsApp API could not be reached.") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("WhatsApp API returned an unreadable response.") from exc


def send_text(recipient: str, body: str) -> dict:
    if not whatsapp_messaging_configured():
        raise RuntimeError("WhatsApp API is not connected yet.")
    to = normalize_whatsapp_number(recipient)
    if not to:
        raise ValueError("WhatsApp # must use a valid international number.")
    text = (body or "").strip()
    if not text:
        raise ValueError("Write a WhatsApp message first.")
    return _json_request(
        f"{_graph_base()}/{_phone_number_id()}/messages",
        method="POST",
        payload={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"preview_url": False, "body": text},
        },
    )


def upload_media(filename: str, mime_type: str, data: bytes) -> str:
    if not whatsapp_messaging_configured():
        raise RuntimeError("WhatsApp API is not connected yet.")
    if not data:
        raise ValueError("The selected WhatsApp file is empty.")

    boundary = "----RSFWhatsApp" + uuid.uuid4().hex
    safe_name = (filename or "attachment").replace('"', "")
    mime = (mime_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").strip()
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"messaging_product\"\r\n\r\nwhatsapp\r\n".encode(),
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{safe_name}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode(),
        data,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    req = Request(
        f"{_graph_base()}/{_phone_number_id()}/media",
        data=b"".join(parts),
        headers={
            "Authorization": f"Bearer {_access_token()}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=40) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_decode_http_error(exc)) from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("WhatsApp media upload failed.") from exc
    media_id = str(payload.get("id") or "").strip()
    if not media_id:
        raise RuntimeError("WhatsApp did not return a media ID.")
    return media_id


def send_media(recipient: str, media_id: str, message_type: str, *, filename: str = "", caption: str = "") -> dict:
    if not whatsapp_messaging_configured():
        raise RuntimeError("WhatsApp API is not connected yet.")
    to = normalize_whatsapp_number(recipient)
    if not to:
        raise ValueError("WhatsApp # must use a valid international number.")
    kind = (message_type or "").strip().lower()
    if kind not in {"image", "video", "audio", "document"}:
        raise ValueError("Unsupported WhatsApp media type.")

    media = {"id": media_id}
    if filename and kind == "document":
        media["filename"] = filename[:240]
    if caption and kind in {"image", "video", "document"}:
        media["caption"] = caption[:1024]

    return _json_request(
        f"{_graph_base()}/{_phone_number_id()}/messages",
        method="POST",
        payload={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to.lstrip("+"),
            "type": kind,
            kind: media,
        },
    )


def message_id_from_response(payload: dict) -> str:
    messages = payload.get("messages") or []
    if not messages:
        return ""
    return str((messages[0] or {}).get("id") or "").strip()


def download_media(media_id: str) -> tuple[bytes, str]:
    info = _json_request(f"{_graph_base()}/{media_id}")
    url = str(info.get("url") or "").strip()
    if not url:
        raise RuntimeError("WhatsApp media URL is unavailable.")
    mime = str(info.get("mime_type") or "application/octet-stream").strip()
    req = Request(url, headers={"Authorization": f"Bearer {_access_token()}"}, method="GET")
    try:
        with urlopen(req, timeout=40) as response:
            data = response.read()
            mime = response.headers.get_content_type() or mime
    except HTTPError as exc:
        raise RuntimeError(_decode_http_error(exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("WhatsApp media could not be downloaded.") from exc
    return data, mime


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = (current_app.config.get("WHATSAPP_APP_SECRET") or "").strip()
    if not secret:
        return False
    supplied = (signature_header or "").strip()
    if not supplied.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied[7:], expected)
