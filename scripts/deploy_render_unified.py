from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/keycastro/RSF-Main-System.git"
EXPECTED_REPO = "keycastro/rsf-main-system"
WEBSITE = "https://realtysystemsfoundry.onrender.com"
PARTNER = "https://partner-rsf.onrender.com"
WEB_SERVICE_ID = "srv-das7540jo6nc73age4fg"

# Only these files are allowed to change in a private-workspace release.
PRIVATE_FILES = [
    "VERSION.txt",
    "config.py",
    "bootstrap.py",
    "app/auth.py",
    "app/background.py",
    "app/client_ops.py",
    "app/credential_vault.py",
    "app/db.py",
    "app/routes.py",
    "app/schema.sql",
    "app/services.py",
    "app/static/css/app.css",
    "app/static/css/workspace_v18.css",
    "app/static/css/workspace_v20.css",
    "app/static/js/app.js",
]
PRIVATE_TEMPLATE_DIR = ROOT / "app" / "templates"

# Keep the deploy workflow itself in GitHub too. This prevents a newer release
# from being installed locally while GitHub still contains an obsolete deployer.
WORKFLOW_FILES = [
    "installers/SETUP_AND_DEPLOY_RSF_MAIN_SYSTEM.bat",
    "installers/SETUP_RSF_MAIN_SYSTEM.bat",
    "deployment/DEPLOY_RSF_LIVE.bat",
    "deployment/PUBLISH_RSF_ONLINE.bat",
    "scripts/PUBLISH_RSF_ONLINE.py",
    "scripts/deploy_render_unified.py",
    "scripts/RECOVER_NEW_RENDER_HOSTING.py",
    "scripts/VERIFY_INSTALLED_SYSTEM.py",
    "PROJECT_STATE.json",
]

# These source areas define the public website and must remain exactly as they are
# in the current GitHub/live source during a private-workspace deployment.
PUBLIC_PROTECTED = [
    "app/public_routes.py",
    "app/seo.py",
    "app/system_templates.py",
    "app/templates/public",
    "app/static/css/public_site.css",
    "app/static/js/public_site.js",
    "app/static/images/about",
    "app/static/images/projects",
    "app/static/images/templates",
    "public",
]


def run(args: list[str], cwd: Path, *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and proc.returncode:
        detail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        raise RuntimeError(detail or f"Command failed ({proc.returncode}): {' '.join(args)}")
    return proc


def text(args: list[str], cwd: Path) -> str:
    return (run(args, cwd, capture=True).stdout or "").strip()


def optional_text(args: list[str], cwd: Path) -> str:
    proc = run(args, cwd, check=False, capture=True)
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def copy_file(rel: str, dest_root: Path) -> None:
    src = ROOT / rel
    if not src.is_file():
        raise RuntimeError(f"Required private-workspace source file is missing: {rel}")
    dst = dest_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def iter_files(path: Path):
    if path.is_file():
        yield path
    elif path.is_dir():
        for item in sorted(path.rglob("*")):
            if item.is_file():
                yield item


def public_hashes(repo_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for rel in PUBLIC_PROTECTED:
        target = repo_root / rel
        if not target.exists():
            continue
        for file in iter_files(target):
            rel_file = file.relative_to(repo_root).as_posix()
            result[rel_file] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def changed_paths(repo_root: Path) -> list[str]:
    # Porcelain status uses two fixed status columns plus one space. Keep leading
    # spaces intact; stripping the whole output would corrupt the first path.
    proc = run(["git", "status", "--porcelain", "--untracked-files=all"], repo_root, capture=True)
    out = proc.stdout or ""
    paths: list[str] = []
    for line in out.splitlines():
        if len(line) < 4 or not line.strip():
            continue
        payload = line[3:].strip()
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        paths.append(payload.replace("\\", "/"))
    return paths


def is_allowed_change(path: str) -> bool:
    if path in PRIVATE_FILES or path in WORKFLOW_FILES:
        return True
    if path.startswith("app/templates/") and path.count("/") == 2 and path.endswith(".html"):
        return True
    return False


def overlay_private_workspace(repo_root: Path) -> None:
    for rel in PRIVATE_FILES + WORKFLOW_FILES:
        copy_file(rel, repo_root)
    for template in sorted(PRIVATE_TEMPLATE_DIR.glob("*.html")):
        rel = template.relative_to(ROOT).as_posix()
        copy_file(rel, repo_root)


def api(method: str, path: str, key: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request("https://api.render.com/v1" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Render API {exc.code}: {detail}") from exc


def deploy_service(key: str, commit_id: str) -> str:
    deployment = api(
        "POST",
        f"/services/{WEB_SERVICE_ID}/deploys",
        key,
        {"commitId": commit_id, "clearCache": "do_not_clear"},
    )
    deploy_id = deployment.get("id") if isinstance(deployment, dict) else None
    if not deploy_id:
        raise RuntimeError("Render did not return a deployment ID.")
    for _ in range(120):
        current = api("GET", f"/services/{WEB_SERVICE_ID}/deploys/{deploy_id}", key)
        status = current.get("status", "") if isinstance(current, dict) else ""
        print("Render status:", status or "waiting")
        if status == "live":
            deployed_commit = ((current or {}).get("commit") or {}).get("id", "")
            if deployed_commit and deployed_commit != commit_id:
                raise RuntimeError(
                    f"Render reported LIVE for a different commit: {deployed_commit}"
                )
            return deploy_id
        if status in {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}:
            raise RuntimeError(f"Render deployment failed: {status}")
        time.sleep(10)
    raise RuntimeError("Timed out while waiting for Render.")


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "RSF-Live-Verify"})
    return urllib.request.urlopen(req, timeout=45)


def verify_live(version: str) -> None:
    with fetch(WEBSITE + "/system/health") as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
        if response.status != 200 or payload.get("status") != "ok" or payload.get("version") != version:
            raise RuntimeError(f"Live version check failed: {payload!r}")

    # partner-rsf is a small static entry/redirect site, so urllib will not
    # execute its JavaScript/meta refresh. Verify that alias points at the
    # unified workspace, then verify the real /app/ login page directly.
    with fetch(PARTNER + "/") as response:
        alias_html = response.read().decode("utf-8", errors="replace")
        if response.status != 200 or WEBSITE + "/app/" not in alias_html:
            raise RuntimeError("Partner Workspace alias is not pointing at the unified /app/ workspace.")
    with fetch(WEBSITE + "/app/") as response:
        final_url = response.geturl()
        login_html = response.read().decode("utf-8", errors="replace")
    if "/app/login" not in final_url:
        raise RuntimeError(f"Partner Workspace did not open the login page: {final_url}")
    if 'name="name"' not in login_html or 'name="email"' in login_html:
        raise RuntimeError("Live Partner Workspace is still using the old email login.")
    if "Password" not in login_html or "Log In" not in login_html:
        raise RuntimeError("Live Name + Password login page is incomplete.")

    # Public site is not changed by this release; still confirm it stays reachable.
    with fetch(WEBSITE + "/") as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status != 200 or "Realty Systems Foundry" not in body:
            raise RuntimeError("Public website live check failed.")


def write_status(version: str, commit_id: str, deploy_id: str | None) -> None:
    runtime = ROOT / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": version,
        "commit": commit_id,
        "render_deploy_id": deploy_id,
        "website": WEBSITE + "/",
        "partner_workspace": PARTNER + "/",
        "live_verified": bool(deploy_id),
        "public_source_preserved": True,
    }
    (runtime / "live_deployment_status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Publish only verified RSF private-workspace changes and optionally deploy them to Render.")
    parser.add_argument("--publish-only", action="store_true", help="Push the safe private-workspace commit but do not trigger Render.")
    args = parser.parse_args(argv)

    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    print("=" * 68)
    print(f" RSF MAIN SYSTEM v{version} - SAFE PRIVATE WORKSPACE LIVE DEPLOY")
    print("=" * 68)
    print("Public website source: PROTECTED / NOT OVERWRITTEN")
    print("Private workspace source: current verified local release")
    print()

    if shutil.which("git") is None:
        raise RuntimeError("Git for Windows is required for live deployment.")

    with tempfile.TemporaryDirectory(prefix="rsf-live-deploy-") as temp_name:
        temp = Path(temp_name)
        repo = temp / "repo"
        print("Getting the current live GitHub source...")
        run(["git", "clone", "--branch", "main", "--single-branch", REPO_URL, str(repo)], temp)
        origin = text(["git", "remote", "get-url", "origin"], repo).lower().removesuffix(".git")
        if EXPECTED_REPO not in origin:
            raise RuntimeError(f"Unexpected GitHub repository: {origin}")

        previous_commit = text(["git", "rev-parse", "HEAD"], repo)
        before_public = public_hashes(repo)
        if not before_public:
            raise RuntimeError("Public website protection check could not read the remote public source.")

        print("Applying private-workspace files only...")
        overlay_private_workspace(repo)

        after_public = public_hashes(repo)
        if before_public != after_public:
            raise RuntimeError("SAFETY STOP: a public website source file changed during private-workspace preparation.")

        changes = changed_paths(repo)
        blocked = [p for p in changes if not is_allowed_change(p)]
        if blocked:
            raise RuntimeError("SAFETY STOP: unexpected files would be published: " + ", ".join(blocked[:20]))
        if not changes:
            commit_id = previous_commit
            print("GitHub source already has these private-workspace changes.")
        else:
            run(["git", "add", "--"] + changes, repo)
            run(["git", "diff", "--cached", "--check"], repo)
            # Use existing identity when available; otherwise set a local release-only identity.
            if not optional_text(["git", "config", "user.name"], repo):
                run(["git", "config", "user.name", "RSF Release"], repo)
            if not optional_text(["git", "config", "user.email"], repo):
                run(["git", "config", "user.email", "rsf-release@users.noreply.github.com"], repo)
            run(["git", "commit", "-m", f"Deploy RSF private workspace v{version}"], repo)
            commit_id = text(["git", "rev-parse", "HEAD"], repo)
            print("Pushing the verified private-workspace commit to GitHub...")
            run(["git", "push", "origin", "HEAD:main"], repo)

        # A successful local commit is not enough. Confirm GitHub main actually
        # points to the exact commit before Render is allowed to deploy it.
        remote_main = text(["git", "ls-remote", "origin", "refs/heads/main"], repo).split()[0]
        if remote_main != commit_id:
            raise RuntimeError(
                f"GitHub verification failed: main is {remote_main or 'unknown'}, expected {commit_id}."
            )
        print("GITHUB VERIFIED OK")
        print("GitHub commit:", commit_id)
        if args.publish_only:
            write_status(version, commit_id, None)
            print("SOURCE PUBLISHED OK")
            print("LIVE RENDER DEPLOYMENT NOT RUN")
            return 0

        key = os.environ.get("RENDER_API_KEY", "").strip()
        if not key:
            print()
            print("Render needs your API key to deploy the verified commit.")
            print("The key is hidden and is not saved by this tool.")
            key = getpass.getpass("Render API key: ").strip()
        if not key:
            raise RuntimeError("Render API key is required. GitHub may be updated, but Render was not deployed.")

        service = api("GET", f"/services/{WEB_SERVICE_ID}", key)
        if (service or {}).get("name") != "realtysystemsfoundry":
            raise RuntimeError("Render service identity check failed. Deployment stopped.")
        service_repo = ((service or {}).get("repo") or "").lower().removesuffix(".git")
        if EXPECTED_REPO not in service_repo:
            raise RuntimeError(f"Render service is linked to an unexpected repository: {service_repo}")
        if ((service or {}).get("branch") or "main") != "main":
            raise RuntimeError("Render service is not linked to the main branch. Deployment stopped.")

        print("Deploying the exact GitHub commit to Render...")
        deploy_id = deploy_service(key, commit_id)
        print("Checking the real live website and workspace...")
        verify_live(version)
        write_status(version, commit_id, deploy_id)
        print()
        print("LIVE VERIFIED OK")
        print("Live version:", version)
        print("GitHub commit:", commit_id)
        print("Public website source: unchanged")
        print("Website:", WEBSITE + "/")
        print("Partner Workspace:", PARTNER + "/")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print()
        print("LIVE DEPLOYMENT FAILED:", exc)
        print("Do not treat this release as complete until LIVE VERIFIED OK is shown.")
        raise SystemExit(1)
