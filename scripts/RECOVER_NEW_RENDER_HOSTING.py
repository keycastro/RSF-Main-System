from __future__ import annotations

import base64
import getpass
import html
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
USERPROFILE = Path(os.environ.get("USERPROFILE") or Path.home())
INSTALLED = USERPROFILE / "Documents" / "RSF Main System"
LOCAL_DB = INSTALLED / "instance" / "rsf_sales_partner.db"
LOCAL_ENV = INSTALLED / ".env"
LOCAL_STATE = INSTALLED / "PROJECT_STATE.json"

WORKSPACE_HINT = "Key Castro"
WEB_SERVICE_ID = "srv-das7540jo6nc73age4fg"
WEB_SERVICE_NAME = "realtysystemsfoundry"
WEB_URL = "https://realtysystemsfoundry.onrender.com"
PARTNER_URL = "https://partner-rsf.onrender.com"
POSTGRES_ID = "dpg-das724t9fdbs73c4t9l0-a"
POSTGRES_NAME = "rsf-main-system-db"
REPO_URL = "https://github.com/keycastro/RSF-Main-System.git"
MIGRATION_SECRET_FILE = "online_attachment_seed.enc"

MIGRATION_TABLES = [
    "users", "account_password_vault", "commission_stages", "partners", "leads", "lead_notes",
    "followups", "sales", "commissions", "sale_corrections", "resources", "duplicate_claims",
    "activity_log", "messages", "message_attachments", "voice_calls", "voice_call_signals", "settings",
    "website_inquiries", "client_conversations", "client_messages", "client_attachments", "client_notifications",
]


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def run(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    p = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if p.returncode:
        detail = ((p.stderr or "") + "\n" + (p.stdout or "")).strip()
        fail(detail or f"Command failed ({p.returncode}): {' '.join(cmd)}")
    return p


def api(method: str, path: str, key: str, body=None, *, label: str = ""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request("https://api.render.com/v1" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "RSF-Render-Recovery/1.11.2")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        where = label or f"{method} {path}"
        if not detail:
            detail = str(getattr(exc, "reason", "") or "empty response body")
        fail(f"Render API {exc.code} during {where}: {detail}")
    except urllib.error.URLError as exc:
        where = label or f"{method} {path}"
        fail(f"Render connection failed during {where}: {exc.reason}")


def _render_cli_candidates() -> list[Path]:
    result: list[Path] = []
    found = shutil.which("render") or shutil.which("render.exe")
    if found:
        result.append(Path(found))
    local = Path(os.environ.get("LOCALAPPDATA") or "")
    if str(local):
        result.extend([
            local / "Microsoft" / "WinGet" / "Links" / "render.exe",
            local / "Programs" / "render" / "render.exe",
        ])
    return [x for x in result if x.is_file()]


def ensure_render_cli() -> Path:
    candidates = _render_cli_candidates()
    if candidates:
        return candidates[0]
    winget = shutil.which("winget") or shutil.which("winget.exe")
    if not winget:
        fail(
            "Render REST connection-info returned 400 and Render CLI is not installed. "
            "WinGet is also unavailable, so the automatic database-link fallback cannot continue."
        )
    print("Render REST connection-info returned 400; installing the official Render CLI fallback...")
    proc = subprocess.run(
        [
            winget, "install", "--id", "render.cli", "--exact",
            "--accept-package-agreements", "--accept-source-agreements", "--silent",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode not in (0,):
        detail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        fail("Could not install the official Render CLI fallback. " + (detail or f"winget exit {proc.returncode}"))
    # WinGet links can appear after PATH is refreshed; check the standard link directly too.
    candidates = _render_cli_candidates()
    if not candidates:
        local = Path(os.environ.get("LOCALAPPDATA") or "")
        links = local / "Microsoft" / "WinGet" / "Links"
        if links.is_dir():
            for item in links.glob("render*.exe"):
                if item.is_file():
                    candidates.append(item)
    if not candidates:
        fail("Render CLI installation completed, but render.exe could not be located. Open a new CMD and rerun this release.")
    return candidates[0]


def render_cli_database_url(key: str) -> str:
    render_exe = ensure_render_cli()
    env = os.environ.copy()
    env["RENDER_API_KEY"] = key
    env["RENDER_OUTPUT"] = "json"
    env["RENDER_WORKSPACE"] = "tea-dam6o6u1egvs738be51g"
    print("Resolving Postgres connection with official Render CLI...")
    proc = subprocess.run(
        [str(render_exe), "pg", "get", POSTGRES_ID, "--include-sensitive-connection-info", "--output", "json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if proc.returncode:
        detail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        fail("Render CLI could not retrieve Postgres connection info: " + (detail or f"exit {proc.returncode}"))
    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        # Some CLI builds can prefix a short informational line. Extract the JSON object safely.
        left = raw.find("{")
        right = raw.rfind("}")
        if left < 0 or right <= left:
            fail("Render CLI returned connection info in an unreadable format.")
        data = json.loads(raw[left:right + 1])
    url = str(
        data.get("internalConnectionString")
        or data.get("internal_connection_string")
        or ((data.get("connectionInfo") or {}).get("internalConnectionString") if isinstance(data, dict) else "")
        or ""
    ).strip()
    if not url:
        fail("Render CLI connected successfully but did not return an internal Postgres connection string.")
    return url


def get_all_env_vars(key: str) -> dict[str, str]:
    result: dict[str, str] = {}
    cursor = ""
    while True:
        path = f"/services/{WEB_SERVICE_ID}/env-vars?limit=100"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        page = api("GET", path, key) or []
        next_cursor = ""
        for item in page:
            row = item.get("envVar", item) if isinstance(item, dict) else {}
            k = str(row.get("key") or "")
            if k:
                result[k] = str(row.get("value") or "")
            if isinstance(item, dict) and item.get("cursor"):
                next_cursor = str(item["cursor"])
        if len(page) < 100 or not next_cursor:
            break
        cursor = next_cursor
    return result


def get_all_secret_files(key: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    cursor = ""
    while True:
        path = f"/services/{WEB_SERVICE_ID}/secret-files?limit=100"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        page = api("GET", path, key) or []
        next_cursor = ""
        for item in page:
            row = item.get("secretFile", item) if isinstance(item, dict) else {}
            name = str(row.get("name") or "")
            if name:
                result.append({"name": name, "content": str(row.get("content") or "")})
            if isinstance(item, dict) and item.get("cursor"):
                next_cursor = str(item["cursor"])
        if len(page) < 100 or not next_cursor:
            break
        cursor = next_cursor
    return result


def put_env_vars(key: str, env_map: dict[str, str]) -> None:
    body = [{"key": k, "value": str(v)} for k, v in sorted(env_map.items()) if k and k != "."]
    api("PUT", f"/services/{WEB_SERVICE_ID}/env-vars", key, body)


def put_secret_files(key: str, files: list[dict[str, str]]) -> None:
    api("PUT", f"/services/{WEB_SERVICE_ID}/secret-files", key, files)


def load_local_env() -> dict[str, str]:
    if not LOCAL_ENV.is_file():
        fail(f"Preserved local .env not found: {LOCAL_ENV}")
    result: dict[str, str] = {}
    for raw in LOCAL_ENV.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip().strip('"').strip("'")
    if not result.get("SECRET_KEY"):
        fail("Preserved local SECRET_KEY is missing. Stopping before production changes.")
    if not result.get("RSF_CREDENTIAL_VAULT_KEY"):
        # Older builds used SECRET_KEY as the vault fallback. Preserve that exact behavior.
        result["RSF_CREDENTIAL_VAULT_KEY"] = result["SECRET_KEY"]
    return result


def load_contact_email() -> str:
    if LOCAL_STATE.is_file():
        try:
            state = json.loads(LOCAL_STATE.read_text(encoding="utf-8"))
            value = str(state.get("public_contact_email") or "").strip()
            if value:
                return value
        except Exception:
            pass
    return "keycastro509@gmail.com"


def encode_value(value):
    if isinstance(value, (bytes, bytearray)):
        return {"__rsf_bytes_b64__": base64.b64encode(bytes(value)).decode("ascii")}
    return value


def build_database_payload() -> str:
    if not LOCAL_DB.is_file():
        fail(f"Preserved local RSF database not found: {LOCAL_DB}")
    conn = sqlite3.connect(str(LOCAL_DB))
    conn.row_factory = sqlite3.Row
    try:
        available = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        payload = {"tables": {}}
        for table in MIGRATION_TABLES:
            rows = []
            if table in available:
                for row in conn.execute(f'SELECT * FROM "{table}"').fetchall():
                    rows.append({key: encode_value(row[key]) for key in row.keys()})
            payload["tables"][table] = rows
        user_count = len(payload["tables"].get("users", []))
        if user_count < 1:
            fail("Local database has no user accounts. Migration stopped.")
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        if len(encoded) > 50000:
            fail(f"Database migration payload is unexpectedly large ({len(encoded)} bytes). Stopping safely.")
        print(f"Preserved database payload ready: {user_count} user account(s).")
        return encoded
    finally:
        conn.close()


def list_preserved_files() -> list[tuple[str, Path]]:
    roots = [
        (INSTALLED / "instance" / "message_uploads", "message_uploads"),
        (INSTALLED / "instance" / "client_attachments", "client_attachments"),
        (INSTALLED / "instance" / "profile_pictures", "profile_pictures"),
    ]
    result: list[tuple[str, Path]] = []
    for folder, kind in roots:
        if not folder.is_dir():
            continue
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                result.append((kind, file))
    return result


def get_current_credentials():
    env = load_local_env()
    secret = env["RSF_CREDENTIAL_VAULT_KEY"] or env["SECRET_KEY"]
    material = __import__("hashlib").sha256(("rsf-account-password-vault-v1:" + secret).encode("utf-8")).digest()
    fernet = Fernet(base64.urlsafe_b64encode(material))
    conn = sqlite3.connect(str(LOCAL_DB))
    conn.row_factory = sqlite3.Row
    try:
        users = conn.execute(
            """SELECT u.id,u.full_name,u.role,u.active,v.encrypted_password
               FROM users u LEFT JOIN account_password_vault v ON v.user_id=u.id
               WHERE u.active=1 ORDER BY CASE WHEN u.role='admin' THEN 0 ELSE 1 END,u.id"""
        ).fetchall()
        creds = []
        for row in users:
            token = row["encrypted_password"]
            if not token:
                continue
            password = fernet.decrypt(str(token).encode("ascii")).decode("utf-8")
            creds.append((str(row["role"]), str(row["full_name"]), password))
        founder = next((x for x in creds if x[0] == "admin"), None)
        partner = next((x for x in creds if x[0] == "partner"), None)
        if not founder:
            fail("Could not recover the current Founder password from the preserved local encrypted vault.")
        return founder, partner
    finally:
        conn.close()


def render_database_url(key: str) -> str:
    print("[Render preflight 2/4] Verifying new Postgres database...")
    db = api("GET", f"/postgres/{POSTGRES_ID}", key, label="Postgres identity check") or {}
    if str(db.get("name") or "") != POSTGRES_NAME:
        fail("Render Postgres identity check failed. Stopping before environment changes.")
    status = str(db.get("status") or "")
    if status not in {"available", "creating"}:
        fail(f"Render Postgres is not available: {status}")
    if status == "creating":
        for attempt in range(1, 31):
            print(f"Waiting for Postgres to become available ({attempt}/30)...")
            time.sleep(5)
            db = api("GET", f"/postgres/{POSTGRES_ID}", key, label="Postgres readiness check") or {}
            status = str(db.get("status") or "")
            if status == "available":
                break
        if status != "available":
            fail("Render Postgres did not become available in time.")
    print("[Render preflight 3/4] Resolving private Postgres connection...")
    try:
        info = api(
            "GET",
            f"/postgres/{POSTGRES_ID}/connection-info",
            key,
            label="Postgres connection-info",
        ) or {}
        url = str(info.get("internalConnectionString") or info.get("internal_connection_string") or "").strip()
        if url:
            return url
    except RuntimeError as exc:
        message = str(exc)
        if "Render API 400" not in message:
            raise
        print("Render REST connection-info returned HTTP 400; using official Render CLI fallback.")
        return render_cli_database_url(key)
    return render_cli_database_url(key)


def verify_service_identity(key: str) -> None:
    print("[Render preflight 1/4] Verifying API key + new web service...")
    # Listing first produces a much clearer authentication diagnostic than jumping
    # straight into a sensitive Postgres call.
    api("GET", "/services?limit=3", key, label="API-key authentication check")
    svc = api("GET", f"/services/{WEB_SERVICE_ID}", key, label="web-service identity check") or {}
    if str(svc.get("name") or "") != WEB_SERVICE_NAME:
        fail("Render web service identity check failed.")
    url = str(((svc.get("serviceDetails") or {}).get("url") or "")).rstrip("/")
    if url and url != WEB_URL:
        fail(f"Unexpected Render web URL: {url}")
    if str(svc.get("branch") or "main") != "main":
        fail("Render web service is not using branch main.")


def publish_verified_source() -> str:
    print("Publishing the corrected private-workspace/deployment source to GitHub...")
    run([sys.executable, str(ROOT / "scripts" / "deploy_render_unified.py"), "--publish-only"], cwd=ROOT)
    p = run(["git", "ls-remote", REPO_URL, "refs/heads/main"], capture=True)
    line = (p.stdout or "").strip()
    if not line:
        fail("Could not verify GitHub main after publishing.")
    return line.split()[0]


def start_deploy(key: str, commit_id: str) -> str:
    d = api("POST", f"/services/{WEB_SERVICE_ID}/deploys", key, {"commitId": commit_id, "clearCache": "do_not_clear"}) or {}
    dep = str(d.get("id") or "")
    if not dep:
        fail("Render did not return a deployment ID.")
    return dep


def wait_deploy(key: str, deploy_id: str, commit_id: str, label: str) -> None:
    for attempt in range(1, 121):
        d = api("GET", f"/services/{WEB_SERVICE_ID}/deploys/{deploy_id}", key) or {}
        status = str(d.get("status") or "")
        print(f"{label}: {status or 'waiting'}")
        if status == "live":
            deployed = str(((d.get("commit") or {}).get("id") or ""))
            if deployed and deployed != commit_id:
                fail(f"Render reported a different live commit: {deployed}")
            return
        if status in {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}:
            fail(f"Render deployment failed: {status}")
        time.sleep(8)
    fail("Timed out waiting for Render deployment.")


def fetch(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": "RSF-Recovery/1.11.2"})
    return urllib.request.urlopen(req, timeout=timeout)


def verify_public_and_login_page(version: str) -> None:
    with fetch(WEB_URL + "/system/health") as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
        if r.status != 200 or data.get("status") != "ok" or data.get("version") != version:
            fail(f"Live health/version check failed: {data!r}")
    with fetch(PARTNER_URL + "/") as r:
        alias = r.read().decode("utf-8", errors="replace")
        if r.status != 200 or WEB_URL + "/app/" not in alias:
            fail("partner-rsf.onrender.com is not pointing to the RSF /app/ workspace.")
    with fetch(WEB_URL + "/app/") as r:
        page = r.read().decode("utf-8", errors="replace")
        final_url = r.geturl()
        if "/app/login" not in final_url:
            fail(f"Private workspace did not reach login: {final_url}")
        if 'name="name"' not in page or 'name="email"' in page or "Password" not in page or "Log In" not in page:
            fail("Live workspace is not showing Name + Password + Log In.")
    with fetch(WEB_URL + "/") as r:
        body = r.read().decode("utf-8", errors="replace")
        if r.status != 200 or "Realty Systems Foundry" not in body:
            fail("Public website live check failed.")


def verify_real_login(name: str, password: str, role_label: str):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "RSF-Recovery-Login-Verify/1.11.2")]
    with opener.open(WEB_URL + "/app/login", timeout=60) as r:
        body = r.read().decode("utf-8", errors="replace")
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
    if not m:
        fail(f"Could not read CSRF token for {role_label} live-login verification.")
    csrf = html.unescape(m.group(1))
    data = urllib.parse.urlencode({"csrf_token": csrf, "name": name, "password": password}).encode("utf-8")
    req = urllib.request.Request(WEB_URL + "/app/login", data=data, method="POST")
    with opener.open(req, timeout=60) as r:
        final_url = r.geturl()
        page = r.read().decode("utf-8", errors="replace")
    if "/app/login" in final_url or 'name="name"' in page:
        fail(f"{role_label} Name + Password did not authenticate on the live workspace.")
    print(f"{role_label} live Name + Password login VERIFIED OK")
    return opener


def authenticated_csrf(opener) -> str:
    with opener.open(WEB_URL + "/app/admin/settings/account-security", timeout=60) as r:
        body = r.read().decode("utf-8", errors="replace")
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
    if not m:
        fail("Could not read authenticated CSRF token for preserved-file migration.")
    return html.unescape(m.group(1))


def multipart_body(fields: dict[str, str], filename: str, content: bytes):
    boundary = "----RSFRecovery" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    safe_name = filename.replace('"', '')
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'.encode())
    chunks.append(b"Content-Type: application/octet-stream\r\n\r\n")
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


def upload_preserved_files(opener, files: list[tuple[str, Path]]) -> int:
    if not files:
        return 0
    csrf = authenticated_csrf(opener)
    uploaded = 0
    for kind, path in files:
        boundary, body = multipart_body(
            {"csrf_token": csrf, "kind": kind, "stored_name": path.name},
            path.name,
            path.read_bytes(),
        )
        req = urllib.request.Request(
            WEB_URL + "/app/admin/recovery/upload-preserved-file",
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with opener.open(req, timeout=120) as r:
            result = json.loads(r.read().decode("utf-8", errors="replace"))
            if r.status != 200 or not result.get("ok"):
                fail(f"Preserved file upload failed for {path.name}.")
        uploaded += 1
        print(f"Preserved file migrated: {path.name}")
    return uploaded


def main() -> int:
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    print("=" * 72)
    print(" RSF NEW RENDER HOSTING RECOVERY + DATA MIGRATION")
    print("=" * 72)
    print("Target website:", WEB_URL)
    print("Target partner workspace:", PARTNER_URL)
    print("Local accounts/data source:", LOCAL_DB)
    print("Public website source: PROTECTED")
    print()

    if not INSTALLED.is_dir() or not LOCAL_DB.is_file() or not LOCAL_ENV.is_file():
        fail("The preserved installed RSF system is incomplete. Run the local setup first.")

    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not api_key:
        print("Render API key is needed once to link the new Postgres and deploy securely.")
        print("The key is hidden and is NOT saved by this tool.")
        api_key = getpass.getpass("Render API key: ").strip()
    if not api_key:
        fail("Render API key was not provided.")

    verify_service_identity(api_key)
    db_url = render_database_url(api_key)
    print("[Render preflight 4/4] Render API + Postgres connection resolved securely.")
    founder, partner = get_current_credentials()
    db_payload = build_database_payload()
    preserved_files = list_preserved_files()

    original_env = get_all_env_vars(api_key)

    local_env = load_local_env()
    production_env = dict(original_env)
    # Preserve local application/security/mail settings without carrying local-only bind values.
    skip_local = {"HOST", "PORT", "PUBLIC_BASE_URL", "TRUSTED_HOSTS", "SESSION_COOKIE_SECURE", "ENVIRONMENT_LABEL", "DATABASE_URL", "DATABASE_PATH"}
    for k, v in local_env.items():
        if k not in skip_local and v != "":
            production_env[k] = v
    production_env["SECRET_KEY"] = local_env["SECRET_KEY"]
    production_env["RSF_CREDENTIAL_VAULT_KEY"] = local_env["RSF_CREDENTIAL_VAULT_KEY"]
    production_env["DATABASE_URL"] = db_url
    production_env["RSF_ENV"] = "production"
    production_env["PUBLIC_BASE_URL"] = WEB_URL
    production_env["TRUSTED_HOSTS"] = "realtysystemsfoundry.onrender.com,partner-rsf.onrender.com"
    production_env["SESSION_COOKIE_SECURE"] = "1"
    production_env["ENVIRONMENT_LABEL"] = "Production"
    production_env["CONTACT_EMAIL"] = local_env.get("CONTACT_EMAIL", "").strip() or load_contact_email()
    production_env["RSF_EMAIL_NAME"] = local_env.get("RSF_EMAIL_NAME", "").strip() or "Realty Systems Foundry"
    production_env["RSF_MIGRATION_PAYLOAD_B64"] = db_payload
    production_env["RSF_DISABLE_BACKGROUND"] = "1"
    production_env["RSF_RECOVERY_UPLOAD_ENABLED"] = "1"

    commit_id = publish_verified_source()
    print("GitHub exact commit:", commit_id)
    print("Configuring new Render service + Postgres securely...")
    put_env_vars(api_key, production_env)

    print("Starting migration deployment...")
    deploy_id = start_deploy(api_key, commit_id)
    wait_deploy(api_key, deploy_id, commit_id, "Migration deploy")
    verify_public_and_login_page(version)
    founder_opener = verify_real_login(founder[1], founder[2], "Founder")
    if partner:
        verify_real_login(partner[1], partner[2], "Partner")
    attachment_count = upload_preserved_files(founder_opener, preserved_files)
    if attachment_count:
        print(f"Protected attachment migration VERIFIED OK: {attachment_count} file(s).")

    print("Migration verified. Removing one-time migration material from Render...")
    final_env = dict(production_env)
    final_env.pop("RSF_MIGRATION_PAYLOAD_B64", None)
    final_env.pop("RSF_DISABLE_BACKGROUND", None)
    final_env.pop("RSF_RECOVERY_UPLOAD_ENABLED", None)
    put_env_vars(api_key, final_env)

    print("Starting clean final deployment...")
    final_deploy_id = start_deploy(api_key, commit_id)
    wait_deploy(api_key, final_deploy_id, commit_id, "Final deploy")
    verify_public_and_login_page(version)
    verify_real_login(founder[1], founder[2], "Founder")
    if partner:
        verify_real_login(partner[1], partner[2], "Partner")

    runtime = INSTALLED / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    marker = {
        "status": "LIVE VERIFIED OK",
        "version": version,
        "github_commit": commit_id,
        "web_service_id": WEB_SERVICE_ID,
        "postgres_id": POSTGRES_ID,
        "website": WEB_URL + "/",
        "partner_workspace": PARTNER_URL + "/",
        "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "local_data_migrated": True,
        "attachment_files_migrated": attachment_count,
    }
    (runtime / "render_recovery_complete.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")

    print()
    print("=" * 72)
    print(" LIVE VERIFIED OK")
    print("=" * 72)
    print("LOCAL VERIFIED OK")
    print("GITHUB VERIFIED OK")
    print("POSTGRES MIGRATION VERIFIED OK")
    print("FOUNDER NAME + PASSWORD LOGIN VERIFIED OK")
    if partner:
        print("PARTNER NAME + PASSWORD LOGIN VERIFIED OK")
    print("Website:", WEB_URL + "/")
    print("Partner Workspace:", PARTNER_URL + "/")
    print("Public website source: unchanged")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print()
        print("NEW RENDER RECOVERY FAILED:", exc)
        print("Do NOT treat the deployment as complete until LIVE VERIFIED OK appears.")
        raise SystemExit(1)
