from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
APP_DIRS = ('app', 'scripts', 'installers', 'deployment', 'docs', 'assets', 'public')
APP_FILES = (
    '.env.example', '.gitignore', 'VERSION.txt', 'requirements.txt', 'requirements-production.txt',
    'config.py', 'bootstrap.py', 'run.py', 'wsgi.py', 'README.md', 'Dockerfile', 'Procfile', 'PROJECT_STATE.json',
)
OBSOLETE_ROOT_ITEMS = (
    'APPLY_UPDATE_AND_DEPLOY_LIVE.bat', 'AUTO_DEPLOY_README.txt', 'CHANGELOG.md', 'DELIVERY_REPORT.md',
    'DEPLOY_RSF_LIVE.bat', 'DEPLOY_UNIFIED_README.txt', 'DEVELOPER_HANDOFF.md', 'LIVE_DEPLOYMENT_STATUS.txt',
    'NEXT_DEVELOPER_READ_THIS_FIRST.md', 'PUBLISH_RSF_ONLINE.bat', 'REALTY_SYSTEMS_FOUNDRY.ico',
    'REALTY_SYSTEMS_FOUNDRY_INBOX_LAUNCHER.ps1', 'REALTY_SYSTEMS_FOUNDRY_LAUNCHER.ps1', 'RELEASE_AUDIT.md',
    'REPOSITORY_AND_DEPLOYMENT_STATUS.txt', 'RSF Partner System Desktop.ico', 'RSF Partner System Launcher.vbs',
    'RSF Partner System.ico', 'Realty Systems Foundry Website Launcher.vbs', 'SECURITY_AND_SHARING_NOTES.md',
    'SETUP_REALTY_SYSTEMS_FOUNDRY.bat', 'SETUP_RSF_PARTNER_SYSTEM.bat', 'START_REALTY_SYSTEMS_FOUNDRY.bat',
    'START_RSF_PARTNER_SYSTEM.bat', 'STOP_REALTY_SYSTEMS_FOUNDRY.bat', 'online_attachment_seed.enc',
    'UNIFIED_RSF_v1.3.0_NOTES.txt', 'UNIFIED_RSF_v1.3.1_NOTES.txt', 'UNIFIED_RSF_v1.3.2_NOTES.txt',
    'UNIFIED_RSF_v1.4.0_NOTES.txt', 'UNIFIED_RSF_v1.5.0_NOTES.txt', 'UNIFIED_RSF_v1.5.2_NOTES.txt',
)


def known_folder(name: str, fallback: Path) -> Path:
    if os.name != 'nt':
        return fallback
    try:
        import winreg
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
        value_name = 'Personal' if name == 'documents' else 'Desktop'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
        return Path(os.path.expandvars(value))
    except Exception:
        return fallback


HOME = Path.home()
DOCUMENTS = known_folder('documents', HOME / 'Documents')
DESKTOP = known_folder('desktop', HOME / 'Desktop')
TARGET = DOCUMENTS / 'RSF Main System'
LEGACY_TARGETS = [
    DOCUMENTS / 'RSF Partner System',
    DOCUMENTS / 'RSF_INTERNAL_SALES_PARTNER_SYSTEM',
    DOCUMENTS / 'RSF_INTERNAL_SALES_PARTNER_SYSTEM_V1.0.0',
]
LEGACY_WEBSITE_TARGETS = [
    DOCUMENTS / 'REALTY_SYSTEMS_FOUNDRY',
    DOCUMENTS / 'REALTY SYSTEMS FOUNDRY',
]
OLD_RECOVERY = DOCUMENTS / 'RSF Recovery'
ROLLBACK = Path(tempfile.gettempdir()) / 'RSF Main System Rollback' / uuid.uuid4().hex


def step(message: str) -> None:
    print(f'\n[{message}]', flush=True)


def parse_env(folder: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    path = folder / '.env'
    if not path.exists():
        return result
    for raw in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if sep:
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def database_path(folder: Path) -> Path:
    configured = parse_env(folder).get('DATABASE_PATH', 'instance/rsf_sales_partner.db')
    p = Path(configured)
    return p if p.is_absolute() else folder / p


def uploads_path(folder: Path) -> Path:
    configured = parse_env(folder).get('MESSAGE_UPLOAD_DIR', 'instance/message_uploads')
    p = Path(configured)
    return p if p.is_absolute() else folder / p


def profile_pictures_path(folder: Path) -> Path:
    configured = parse_env(folder).get('PROFILE_PICTURE_DIR', 'instance/profile_pictures')
    p = Path(configured)
    return p if p.is_absolute() else folder / p


def client_attachments_path(folder: Path) -> Path:
    configured = parse_env(folder).get('CLIENT_ATTACHMENT_DIR', 'instance/client_attachments')
    p = Path(configured)
    return p if p.is_absolute() else folder / p


def rsf_port(folder: Path) -> int:
    try:
        value = int(parse_env(folder).get('PORT', '5078'))
        return value if 1024 <= value <= 65535 else 5078
    except Exception:
        return 5078


def rsf_is_serving(port: int) -> bool:
    """Return True for any RSF listener on the configured port, including an older build.

    Older RSF versions can return 404 for /app/login while still adding the X-RSF-App
    header in their error handler. urllib raises HTTPError for that response, so the old
    implementation incorrectly treated a running old RSF server as absent and left it
    occupying the port during an update.
    """
    try:
        import urllib.error
        import urllib.request
        request = urllib.request.Request(
            f'http://127.0.0.1:{port}/app/login',
            headers={'User-Agent': 'RSF-Installer/1.3.0'},
        )
        try:
            with urllib.request.urlopen(request, timeout=1.0) as response:
                return response.headers.get('X-RSF-App') == 'partner-system'
        except urllib.error.HTTPError as exc:
            return exc.headers.get('X-RSF-App') == 'partner-system'
    except Exception:
        return False


def exact_rsf_version_is_serving(port: int, expected_version: str) -> bool:
    try:
        import json
        import urllib.request
        request = urllib.request.Request(
            f'http://127.0.0.1:{port}/system/health',
            headers={'User-Agent': f'RSF-Installer/{expected_version}'},
        )
        with urllib.request.urlopen(request, timeout=1.0) as response:
            if response.status != 200 or response.headers.get('X-RSF-App') != 'partner-system':
                return False
            payload = json.loads(response.read().decode('utf-8', errors='replace'))
            return payload.get('status') == 'ok' and payload.get('version') == expected_version
    except Exception:
        return False


def stop_rsf_processes(folder: Path) -> None:
    """Stop only the verified RSF server listener, never arbitrary Python processes.

    Older installers searched all Python command lines for the RSF folder path.
    When setup itself was launched by the installed virtual environment, that could
    match and kill the parent installer process.  We now verify the HTTP listener
    first and then terminate only the PID listening on RSF's configured port.
    """
    if os.name != 'nt' or not folder.exists():
        return

    port = rsf_port(folder)
    if not rsf_is_serving(port):
        return

    try:
        result = subprocess.run(
            ['netstat', '-ano', '-p', 'tcp'],
            capture_output=True, text=True, errors='replace', timeout=10,
        )
        pids: list[int] = []
        for raw in result.stdout.splitlines():
            parts = raw.split()
            if len(parts) < 5 or parts[0].upper() != 'TCP' or parts[3].upper() != 'LISTENING':
                continue
            local = parts[1]
            pid_text = parts[-1]
            if local.endswith(f':{port}') and pid_text.isdigit():
                pid = int(pid_text)
                if pid != os.getpid() and pid not in pids:
                    pids.append(pid)
        for pid in pids:
            subprocess.run(
                ['taskkill', '/PID', str(pid), '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
        if pids:
            time.sleep(0.6)
    except Exception:
        # Failure to stop a server will surface naturally later if a file or port
        # cannot be updated; never broaden this into killing unrelated processes.
        pass


def snapshot_database(folder: Path, destination: Path) -> tuple[Path | None, Path]:
    source = database_path(folder).resolve()
    if not source.exists():
        return None, source
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / 'rsf_sales_partner.db'
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original, sqlite3.connect(output) as backup:
        original.backup(backup)
        if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Database safety copy failed integrity verification.')
    return output, source


def preserve_state(folder: Path) -> dict:
    state = {'source': folder, 'env': None, 'db_snapshot': None, 'db_original': None, 'uploads_snapshot': None, 'uploads_original': None, 'profile_pictures_snapshot': None, 'profile_pictures_original': None, 'client_attachments_snapshot': None, 'client_attachments_original': None}
    if not folder.exists():
        return state
    env_file = folder / '.env'
    if env_file.exists():
        state['env'] = env_file.read_bytes()
    db_snapshot, db_original = snapshot_database(folder, ROLLBACK / 'database')
    state['db_snapshot'], state['db_original'] = db_snapshot, db_original
    up = uploads_path(folder)
    state['uploads_original'] = up
    if up.exists():
        dest = ROLLBACK / 'message_uploads'
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(up, dest)
        state['uploads_snapshot'] = dest
    pics = profile_pictures_path(folder)
    state['profile_pictures_original'] = pics
    if pics.exists():
        dest = ROLLBACK / 'profile_pictures'
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(pics, dest)
        state['profile_pictures_snapshot'] = dest
    client_files = client_attachments_path(folder)
    state['client_attachments_original'] = client_files
    if client_files.exists():
        dest = ROLLBACK / 'client_attachments'
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(client_files, dest)
        state['client_attachments_snapshot'] = dest
    return state


def backup_app(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    backup = ROLLBACK / 'application'
    backup.mkdir(parents=True, exist_ok=True)
    for name in APP_DIRS:
        src = folder / name
        if src.exists():
            shutil.copytree(src, backup / name, dirs_exist_ok=True)
    for name in (*APP_FILES, *OBSOLETE_ROOT_ITEMS):
        src = folder / name
        if src.exists():
            (backup / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, backup / name)
    return backup


def restore_app(backup: Path | None) -> None:
    if not backup or not backup.exists():
        return
    for name in APP_DIRS:
        dst = TARGET / name
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        src = backup / name
        if src.exists():
            shutil.copytree(src, dst)
    for name in (*APP_FILES, *OBSOLETE_ROOT_ITEMS):
        src = backup / name
        if src.exists():
            shutil.copy2(src, TARGET / name)


def restore_private(state: dict, translate_to_target: bool = False) -> None:
    if state.get('env') is not None:
        (TARGET / '.env').write_bytes(state['env'])
    snap = state.get('db_snapshot')
    if snap and Path(snap).exists():
        dest = database_path(TARGET) if translate_to_target else Path(state['db_original'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ('', '-wal', '-shm'):
            try:
                Path(str(dest) + suffix).unlink(missing_ok=True)
            except OSError:
                pass
        shutil.copy2(snap, dest)
    uploads = state.get('uploads_snapshot')
    if uploads and Path(uploads).exists():
        dest = uploads_path(TARGET) if translate_to_target else Path(state['uploads_original'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(uploads, dest)
    pictures = state.get('profile_pictures_snapshot')
    if pictures and Path(pictures).exists():
        dest = profile_pictures_path(TARGET) if translate_to_target else Path(state['profile_pictures_original'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(pictures, dest)
    client_files = state.get('client_attachments_snapshot')
    if client_files and Path(client_files).exists():
        dest = client_attachments_path(TARGET) if translate_to_target else Path(state['client_attachments_original'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(client_files, dest)


def copy_application() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in APP_DIRS:
        src, dst = SOURCE / name, TARGET / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in APP_FILES:
        src = SOURCE / name
        if src.exists():
            shutil.copy2(src, TARGET / name)
    # Restore the original website Git/Render deployment identity into the one unified folder.
    # Never overwrite an existing repo; only recover it when the prior standalone website folder was removed.
    src_git = SOURCE / '.git'
    dst_git = TARGET / '.git'
    if src_git.exists() and not dst_git.exists():
        shutil.copytree(src_git, dst_git)
    (TARGET / 'instance').mkdir(exist_ok=True)
    (TARGET / 'runtime' / 'logs').mkdir(parents=True, exist_ok=True)


def clean_obsolete_root_clutter() -> None:
    """Remove only known superseded files after their organized copies are installed."""
    for name in OBSOLETE_ROOT_ITEMS:
        path = TARGET / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            try:
                path.unlink()
                print(f'Moved out of root: {name}')
            except OSError as exc:
                raise RuntimeError(f'Could not remove obsolete root file {name}: {exc}')
    old_logs = TARGET / 'logs'
    new_logs = TARGET / 'runtime' / 'logs'
    if old_logs.exists():
        new_logs.mkdir(parents=True, exist_ok=True)
        for child in old_logs.iterdir():
            dest = new_logs / child.name
            if dest.exists():
                continue
            shutil.move(str(child), str(dest))
        try:
            old_logs.rmdir()
        except OSError:
            pass


def create_venv() -> Path:
    python = TARGET / '.venv' / 'Scripts' / 'python.exe'
    if python.exists():
        return python
    subprocess.run([sys.executable, '-m', 'venv', str(TARGET / '.venv')], check=True)
    if not python.exists():
        raise RuntimeError('Could not create the Python environment.')
    return python


def run_checked(args: list[str], cwd: Path = TARGET) -> None:
    proc = subprocess.run(args, cwd=str(cwd))
    if proc.returncode:
        raise RuntimeError(f'Command failed with exit code {proc.returncode}: {args[0]}')


def create_shortcuts() -> tuple[Path, Path]:
    """Create two Desktop entry points into the same unified RSF application.

    The website shortcut opens the public root while the Partner System shortcut
    opens the private workspace.  Both launch the exact same installed server,
    codebase, database, and process.
    """
    DESKTOP.mkdir(parents=True, exist_ok=True)
    target = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'wscript.exe'
    partner_launcher = TARGET / 'installers' / 'launchers' / 'RSF Partner System Launcher.vbs'
    website_launcher = TARGET / 'installers' / 'launchers' / 'Realty Systems Foundry Website Launcher.vbs'
    partner_icon = TARGET / 'assets' / 'icons' / 'RSF Partner System Desktop.ico'
    website_icon = TARGET / 'app' / 'static' / 'images' / 'brand' / 'KEY_CASTRO.ico'
    if not website_icon.exists():
        website_icon = TARGET / 'assets' / 'icons' / 'RSF Partner System Desktop.ico'

    shortcuts = (
        (DESKTOP / 'RSF Partner System.lnk', partner_launcher, partner_icon, 'Open RSF private Founder and Partner workspace'),
        (DESKTOP / 'Realty Systems Foundry Website.lnk', website_launcher, website_icon, 'Open Realty Systems Foundry public website'),
    )

    def q(value: Path | str) -> str:
        return str(value).replace('"', '""')

    created: list[Path] = []
    for index, (shortcut, launcher, icon, description) in enumerate(shortcuts, start=1):
        script = ROLLBACK / f'create_shortcut_{index}.vbs'
        script.write_text(
            'Set shell = CreateObject("WScript.Shell")\n'
            f'Set shortcut = shell.CreateShortcut("{q(shortcut)}")\n'
            f'shortcut.TargetPath = "{q(target)}"\n'
            f'shortcut.Arguments = """{q(launcher)}"""\n'
            f'shortcut.WorkingDirectory = "{q(TARGET)}"\n'
            f'shortcut.Description = "{description}"\n'
            f'shortcut.IconLocation = "{q(icon)},0"\n'
            'shortcut.Save\n',
            encoding='utf-8',
        )
        try:
            shortcut.unlink(missing_ok=True)
        except OSError:
            pass
        run_checked(['cscript.exe', '//nologo', str(script)], cwd=TARGET)
        if not shortcut.exists():
            raise RuntimeError(f'Desktop shortcut could not be created: {shortcut.name}')
        created.append(shortcut)
    return created[0], created[1]


def clean_old_generated() -> None:
    candidates = [OLD_RECOVERY, *LEGACY_TARGETS]
    if DOCUMENTS.exists():
        for p in DOCUMENTS.iterdir():
            if p.is_dir() and (p.name.startswith('RSF Partner System_backup_') or p.name.startswith('RSF Partner System Backup') or p.name.startswith('RSF Partner System - Backup')):
                candidates.append(p)
    target_resolved = TARGET.resolve()
    for p in candidates:
        try:
            if p.exists() and p.resolve() != target_resolved:
                shutil.rmtree(p)
                print(f'Removed old RSF-generated folder: {p}')
        except Exception:
            print(f'Could not remove old RSF-generated folder automatically: {p}')



def _make_writable_and_retry(func, path, exc_info) -> None:
    """shutil.rmtree callback for Windows read-only Git/object files."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except Exception:
        raise exc_info[1]


def force_remove_tree(folder: Path) -> None:
    """Remove a known legacy project tree without touching user ZIP archives.

    Old Git object files can carry Windows read-only/hidden/system attributes.
    Clear those attributes first, then retry read-only files through chmod.
    """
    if not folder.exists():
        return
    if os.name == 'nt':
        subprocess.run(
            ['attrib', '-R', '-H', '-S', str(folder / '*'), '/S', '/D'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=30,
        )
        try:
            os.chmod(folder, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        except OSError:
            pass
    shutil.rmtree(folder, onerror=_make_writable_and_retry)


def remove_legacy_website_folder_after_verification() -> None:
    """Remove only known old standalone website folders after the unified app is live.

    User-created ZIP archives are deliberately left alone. The goal is one active RSF
    project folder in Documents, not destructive cleanup of the user's archives.
    """
    target_resolved = TARGET.resolve()
    for folder in LEGACY_WEBSITE_TARGETS:
        if not folder.exists() or folder.resolve() == target_resolved:
            continue
        try:
            force_remove_tree(folder)
            if folder.exists():
                raise RuntimeError('folder still exists after deletion attempt')
            print(f'Removed old standalone website folder: {folder}')
        except Exception as exc:
            raise RuntimeError(
                f'Could not remove old standalone website folder {folder}. '
                f'Close any File Explorer/Git/editor window using that folder and run setup again. Details: {exc}'
            )

def main() -> int:
    version = (SOURCE / 'VERSION.txt').read_text(encoding='utf-8').strip()
    print(f'RSF MAIN SYSTEM - V{version} SETUP')
    print(f'Install location: {TARGET}')
    print('Desktop launchers: Realty Systems Foundry Website + RSF Partner System')
    print('Installer engine: Python (PowerShell not required)')
    print('Documents rule: one RSF project folder only')
    ROLLBACK.mkdir(parents=True, exist_ok=True)

    state_source = TARGET if TARGET.exists() else next((p for p in LEGACY_TARGETS if p.exists()), None)
    state = {'source': None, 'env': None, 'db_snapshot': None, 'db_original': None, 'uploads_snapshot': None, 'uploads_original': None, 'profile_pictures_snapshot': None, 'profile_pictures_original': None}
    app_backup = None
    try:
        if state_source:
            step('Protecting your existing RSF data temporarily')
            stop_rsf_processes(state_source)
            state = preserve_state(state_source)
        stop_rsf_processes(TARGET)

        if TARGET.exists() and SOURCE.resolve() != TARGET.resolve():
            app_backup = backup_app(TARGET)

        step('Updating Documents\\RSF Main System')
        copy_application()
        if state_source and state_source.resolve() != TARGET.resolve():
            restore_private(state, translate_to_target=True)
        elif state.get('env') is not None:
            # Same canonical folder: application copy intentionally leaves runtime files in place,
            # but re-write .env from the verified temporary copy for certainty.
            (TARGET / '.env').write_bytes(state['env'])

        step('Preparing Python')
        venv_python = create_venv()

        step('Installing required packages')
        run_checked([str(venv_python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'requirements.txt'])

        step('Updating the database safely')
        run_checked([str(venv_python), 'bootstrap.py'])

        step('Keeping your login accounts')
        if os.environ.get('RSF_SETUP_ADMIN_PASSWORD') or os.environ.get('RSF_SETUP_PARTNER_PASSWORD'):
            run_checked([str(venv_python), 'scripts\\configure_local_logins.py'])
        else:
            print('Existing account emails and passwords were not changed.')

        step('Organizing the project root')
        clean_obsolete_root_clutter()

        step('Running verification')
        run_checked([str(venv_python), 'scripts\\SMOKE_CHECK.py'])
        run_checked([str(venv_python), 'scripts\\VERIFY_INSTALLED_SYSTEM.py'])

        step('Cleaning old developer files')
        for name in ('tests', 'audit_artifacts', '__pycache__', '.pytest_cache', 'RUN_TESTS.bat'):
            path = TARGET / name
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                try: path.unlink()
                except OSError: pass

        step('Creating the Desktop launcher')
        partner_shortcut, website_shortcut = create_shortcuts()

        step('Cleaning old RSF-generated folders')
        clean_old_generated()

        step('Preparing online launchers')
        print('Website launcher target: https://realtysystemsfoundry.onrender.com/')
        print('Partner launcher target: https://partner-rsf.onrender.com/')

        step('Removing the old standalone website folder')
        remove_legacy_website_folder_after_verification()

        print('\nUPDATE VERIFIED OK')
        print(f'Only project folder: {TARGET}')
        print(f'Website Desktop shortcut: {website_shortcut}')
        print(f'Partner Desktop shortcut: {partner_shortcut}')
        print('Public website: https://realtysystemsfoundry.onrender.com/')
        print('Private workspace: https://partner-rsf.onrender.com/')
        print(f'Only RSF project folder in Documents: {TARGET}')
        print('PowerShell dependency: REMOVED from setup and launcher')
        shutil.rmtree(ROLLBACK, ignore_errors=True)
        return 0
    except Exception as exc:
        print('\nUPDATE FAILED - restoring your previous application and database.')
        rollback_ok = True
        try:
            restore_app(app_backup)
        except Exception as rollback_exc:
            rollback_ok = False
            print(f'Application rollback warning: {rollback_exc}')
        try:
            if state.get('db_snapshot'):
                restore_private(state, translate_to_target=(state_source is not None and state_source.resolve() != TARGET.resolve()))
        except Exception as rollback_exc:
            rollback_ok = False
            print(f'Private-data rollback warning: {rollback_exc}')
        if rollback_ok:
            shutil.rmtree(ROLLBACK, ignore_errors=True)
            print('Previous working version restored. No extra Documents project folder was created.')
        else:
            print(f'A temporary recovery copy remains in Windows TEMP: {ROLLBACK}')
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
