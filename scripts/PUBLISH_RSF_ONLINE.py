from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_REMOTE = "renderdeploy"
EXPECTED_REMOTE = "keycastro/RSF-Main-System"
PUBLISH_FILES = [
    "app",
    "scripts",
    "installers",
    "deployment",
    "docs",
    "assets",
    ".env.example",
    ".gitignore",
    "config.py",
    "bootstrap.py",
    "wsgi.py",
    "run.py",
    "requirements.txt",
    "requirements-production.txt",
    "VERSION.txt",
    "Procfile",
    "Dockerfile",
    "README.md",
    "PROJECT_STATE.json",
]
STALE_DEPLOY_PATHS = [
    "APPLY_UPDATE_AND_DEPLOY_LIVE.bat",
    "AUTO_DEPLOY_README.txt",
    "CHANGELOG.md",
    "DELIVERY_REPORT.md",
    "DEPLOY_RSF_LIVE.bat",
    "DEPLOY_UNIFIED_README.txt",
    "DEVELOPER_HANDOFF.md",
    "LIVE_DEPLOYMENT_STATUS.txt",
    "NEXT_DEVELOPER_READ_THIS_FIRST.md",
    "PUBLISH_RSF_ONLINE.bat",
    "REALTY_SYSTEMS_FOUNDRY.ico",
    "REALTY_SYSTEMS_FOUNDRY_INBOX_LAUNCHER.ps1",
    "REALTY_SYSTEMS_FOUNDRY_LAUNCHER.ps1",
    "RELEASE_AUDIT.md",
    "REPOSITORY_AND_DEPLOYMENT_STATUS.txt",
    "RSF Partner System Desktop.ico",
    "RSF Partner System Launcher.vbs",
    "RSF Partner System.ico",
    "Realty Systems Foundry Website Launcher.vbs",
    "SECURITY_AND_SHARING_NOTES.md",
    "SETUP_REALTY_SYSTEMS_FOUNDRY.bat",
    "SETUP_RSF_PARTNER_SYSTEM.bat",
    "START_REALTY_SYSTEMS_FOUNDRY.bat",
    "START_RSF_PARTNER_SYSTEM.bat",
    "STOP_REALTY_SYSTEMS_FOUNDRY.bat",
    "online_attachment_seed.enc",
    "UNIFIED_RSF_v1.3.0_NOTES.txt",
    "UNIFIED_RSF_v1.3.1_NOTES.txt",
    "UNIFIED_RSF_v1.3.2_NOTES.txt",
    "UNIFIED_RSF_v1.4.0_NOTES.txt",
    "UNIFIED_RSF_v1.5.0_NOTES.txt",
    "UNIFIED_RSF_v1.5.2_NOTES.txt",
]


def run(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(
        list(args), cwd=ROOT, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and result.returncode:
        detail = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
        raise RuntimeError(detail or f"Command failed ({result.returncode}): {' '.join(args)}")
    return result


def text(*args: str) -> str:
    return (run(*args, capture=True).stdout or "").strip()


def copy_item(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    print("=" * 64)
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    print(f" RSF MAIN SYSTEM v{version} - PUBLISH UNIFIED SOURCE ONLINE")
    print("=" * 64)
    print("Local source:", ROOT)
    print("Render target: https://realtysystemsfoundry.onrender.com")
    print()

    if not (ROOT / ".git").is_dir():
        raise RuntimeError("Git metadata is missing from RSF Main System. Setup stopped before publishing.")
    if shutil.which("git") is None:
        raise RuntimeError("Git for Windows is not installed or not available in CMD PATH.")

    remote = text("git", "remote", "get-url", DEPLOY_REMOTE)
    normalized = remote.lower().removesuffix(".git")
    if EXPECTED_REMOTE not in normalized:
        raise RuntimeError(f"Unexpected Render Git remote: {remote}")
    print("Verified Render source repo:", remote)

    # Explicit private-data guard. These paths must never be part of this public deployment repo.
    forbidden = [
        ROOT / ".env",
        ROOT / "instance" / "rsf_sales_partner.db",
        ROOT / "ONLINE_MIGRATION_PAYLOAD_B64.txt",
        ROOT / "ONLINE_ATTACHMENT_KEY.txt",
    ]
    tracked = set(text("git", "ls-files").splitlines())
    for path in forbidden:
        try:
            rel = path.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if rel in tracked:
            raise RuntimeError(f"SECURITY STOP: private file is tracked by Git: {rel}")

    # Snapshot the complete reviewed organized project source before aligning the Git branch with the
    # current Render remote. Runtime/private local data is intentionally excluded.
    snap = Path(tempfile.mkdtemp(prefix="rsf-online-source-"))
    try:
        for name in PUBLISH_FILES:
            src = ROOT / name
            if not src.exists():
                raise RuntimeError(f"Required deployment file is missing: {name}")
            copy_item(src, snap / name)

        print("Fetching current Render deployment branch...")
        run("git", "fetch", DEPLOY_REMOTE, "main")

        print("Aligning deployment workspace with renderdeploy/main...")
        run("git", "reset", "--hard", f"{DEPLOY_REMOTE}/main")

        # Replace organized source directories completely so stale pre-organization
        # files cannot survive a reset to the previous deployment commit.
        for name in PUBLISH_FILES:
            src = snap / name
            dst = ROOT / name
            if src.is_dir() and dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            copy_item(src, dst)

        # Remove only known superseded production paths from the old root layout.
        for stale in STALE_DEPLOY_PATHS:
            run("git", "rm", "-r", "-f", "--ignore-unmatch", stale, check=False)

        # Stage the reviewed organized project source. Private runtime directories are never staged.
        run("git", "add", "--", *PUBLISH_FILES)
        run("git", "diff", "--cached", "--check")

        changed = run("git", "diff", "--cached", "--quiet", check=False).returncode == 1
        if changed:
            version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
            run("git", "commit", "-m", f"Deploy RSF Main System v{version} unified online app")
        else:
            print("Unified deploy source already matches the current deployment commit.")

        commit = text("git", "rev-parse", "HEAD")
        print("Deployment commit:", commit)
        print("Pushing unified source to Render-linked GitHub repo...")
        run("git", "push", DEPLOY_REMOTE, "HEAD:main")
        print()
        print("SOURCE PUSH VERIFIED OK")
        print("Git commit:", commit)
        print("Next: Render deploy can now be triggered for this exact commit.")
        return 0
    finally:
        shutil.rmtree(snap, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("\nPUBLISH FAILED:", exc)
        print("The current live Render website was not intentionally redeployed by this script.")
        raise SystemExit(1)
