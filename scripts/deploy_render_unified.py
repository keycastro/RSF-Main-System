from __future__ import annotations

import getpass
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "keycastro/RSF-Main-System"
WEBSITE = "https://realtysystemsfoundry.onrender.com"
PARTNER = "https://partner-rsf.onrender.com"
WEB_SERVICE_ID = "srv-das7540jo6nc73age4fg"


def request_json(url: str, *, method: str = "GET", headers=None, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else None


def github_main_commit() -> str:
    payload = request_json(
        f"https://api.github.com/repos/{REPO}/commits/main",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "RSF-Deploy"},
    )
    sha = str((payload or {}).get("sha") or "").strip()
    if len(sha) != 40:
        raise RuntimeError("Could not resolve the exact GitHub main commit.")
    return sha


def github_main_version() -> str:
    req = urllib.request.Request(
        f"https://raw.githubusercontent.com/{REPO}/main/VERSION.txt",
        headers={"User-Agent": "RSF-Deploy"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace").strip()


def render_api(method: str, path: str, key: str, body=None):
    try:
        return request_json(
            "https://api.render.com/v1" + path,
            method=method,
            headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
            body=body,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Render API {exc.code}: {detail}") from exc


def deploy_exact_main(key: str, commit_id: str) -> str:
    deployment = render_api(
        "POST",
        f"/services/{WEB_SERVICE_ID}/deploys",
        key,
        {"commitId": commit_id, "clearCache": "do_not_clear"},
    )
    deploy_id = str((deployment or {}).get("id") or "")
    if not deploy_id:
        raise RuntimeError("Render did not return a deployment ID.")

    for _ in range(120):
        current = render_api("GET", f"/services/{WEB_SERVICE_ID}/deploys/{deploy_id}", key)
        status = str((current or {}).get("status") or "")
        print("Render status:", status or "waiting")
        if status == "live":
            deployed = str(((current or {}).get("commit") or {}).get("id") or "")
            if deployed and deployed != commit_id:
                raise RuntimeError(f"Render deployed {deployed}, expected {commit_id}.")
            return deploy_id
        if status in {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}:
            raise RuntimeError(f"Render deployment failed: {status}")
        time.sleep(10)
    raise RuntimeError("Timed out waiting for Render deployment.")


def fetch(url: str):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "RSF-Live-Verify"}),
        timeout=60,
    )


def verify_live(expected_version: str) -> None:
    with fetch(WEBSITE + "/system/health") as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
        if response.status != 200 or payload.get("status") != "ok":
            raise RuntimeError(f"Health check failed: {payload!r}")
        if payload.get("version") != expected_version:
            raise RuntimeError(
                f"Live version is {payload.get('version')!r}; expected {expected_version!r}."
            )

    with fetch(WEBSITE + "/app/") as response:
        final_url = response.geturl()
        body = response.read().decode("utf-8", errors="replace")
        if "/app/login" not in final_url or "Log In" not in body:
            raise RuntimeError("Private workspace login verification failed.")

    with fetch(WEBSITE + "/") as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status != 200 or "Realty Systems Foundry" not in body:
            raise RuntimeError("Public website verification failed.")


def main() -> int:
    local_version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    main_version = github_main_version()
    if local_version != main_version:
        raise RuntimeError(
            f"SAFE STOP: local version {local_version!r} does not match GitHub main {main_version!r}. "
            "Merge the verified PR first."
        )

    commit_id = github_main_commit()
    print("GitHub main:", commit_id)
    print("Version:", main_version)
    print("Source publishing is intentionally disabled here; this tool deploys merged main only.")

    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        key = getpass.getpass("Render API key (hidden, not saved): ").strip()
    if not key:
        raise RuntimeError("Render API key is required.")

    service = render_api("GET", f"/services/{WEB_SERVICE_ID}", key)
    if str((service or {}).get("name") or "") != "realtysystemsfoundry":
        raise RuntimeError("Unexpected Render service.")
    if str((service or {}).get("branch") or "main") != "main":
        raise RuntimeError("Render service is not linked to main.")

    deploy_id = deploy_exact_main(key, commit_id)
    verify_live(main_version)
    print("LIVE VERIFIED OK")
    print("Deploy:", deploy_id)
    print("Commit:", commit_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
