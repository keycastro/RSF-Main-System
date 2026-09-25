from __future__ import annotations
import getpass, json, os, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'PROJECT_STATE.json'
LIVE = 'https://realtysystemsfoundry.onrender.com'
SERVICE_ID = 'srv-daom5h0ae00c73c3qt70'


def run(*args, check=True):
    p = subprocess.run(list(args), cwd=ROOT, text=True)
    if check and p.returncode:
        raise RuntimeError(f'Command failed ({p.returncode}): {" ".join(args)}')
    return p


def capture(*args):
    p = subprocess.run(list(args), cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip() or f'Command failed: {args[0]}')
    return p.stdout.strip()


def api(method, path, key, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request('https://api.render.com/v1' + path, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + key)
    req.add_header('Accept', 'application/json')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors='replace')
        raise RuntimeError(f'Render API {e.code}: {msg}') from e


def live_ok(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'RSF-Deploy/1.4.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    print('RSF UNIFIED v1.4.0 - SAFE LIVE DEPLOY PREFLIGHT')
    print('Live website:', LIVE)
    if not (ROOT / '.git').exists():
        raise RuntimeError('Unified folder is missing the restored website Git metadata.')
    origin = capture('git','remote','get-url','origin')
    deploy = capture('git','remote','get-url','renderdeploy')
    print('Primary Git remote:', origin)
    print('Render deploy remote:', deploy)
    if 'RSF-Main-System' not in deploy:
        raise RuntimeError('Unexpected Render deployment remote. Stopping before any push.')

    # Never deploy private runtime material.
    status = capture('git','status','--porcelain')
    dangerous = [line for line in status.splitlines() if any(x in line for x in [' .env',' instance/',' logs/','.db','.sqlite'])]
    if dangerous:
        raise RuntimeError('Private/runtime files appear in Git status. Deployment blocked:\n' + '\n'.join(dangerous))

    key = os.environ.get('RENDER_API_KEY','').strip() or getpass.getpass('Render API key (hidden): ').strip()
    if not key:
        raise RuntimeError('Render API key is required. Nothing was changed.')

    service = api('GET', f'/services/{SERVICE_ID}', key)
    print('Render service:', service.get('name', SERVICE_ID) if isinstance(service, dict) else SERVICE_ID)
    disks = api('GET', f'/disks?serviceId={SERVICE_ID}&limit=20', key) or []
    disk_rows = [x.get('disk', x) for x in disks if isinstance(x, dict)]
    suitable = [d for d in disk_rows if d.get('mountPath') in ('/var/data','/opt/render/project/src/instance')]
    if not suitable:
        raise RuntimeError(
            'SAFE STOP: the unified app currently uses SQLite + file uploads, but this Render service has no '
            'persistent disk mounted at /var/data (or the instance path). Render filesystems are ephemeral. '
            'Deploying now could lose Partner/client data on restart. Add a persistent disk first, then rerun.'
        )
    print('Persistent disk OK:', suitable[0].get('mountPath'))

    print('\nGit status:')
    run('git','status','--short')
    print('\nThis tool will not auto-commit unknown local edits. Commit the verified unified release first, then rerun.')
    head = capture('git','rev-parse','HEAD')
    branch = capture('git','branch','--show-current')
    if branch != 'main':
        raise RuntimeError(f'Expected main branch, found {branch!r}.')

    # Require clean tree; installer/release workflow can commit explicitly.
    if capture('git','status','--porcelain'):
        raise RuntimeError('Working tree is not clean. Review/commit the unified release before live deploy.')

    print('Pushing exact unified commit to deployment remote...')
    run('git','push','renderdeploy','main')
    deploy_obj = api('POST', f'/services/{SERVICE_ID}/deploys', key, {'commitId': head, 'clearCache':'do_not_clear'})
    deploy_id = deploy_obj.get('id') if isinstance(deploy_obj, dict) else None
    if not deploy_id:
        raise RuntimeError('Render did not return a deploy ID.')
    print('Deploy started:', deploy_id)
    for _ in range(90):
        d = api('GET', f'/services/{SERVICE_ID}/deploys/{deploy_id}', key)
        status = d.get('status','') if isinstance(d, dict) else ''
        print('  status:', status)
        if status == 'live':
            break
        if status in {'build_failed','update_failed','pre_deploy_failed','canceled','deactivated'}:
            raise RuntimeError(f'Render deploy failed with status: {status}')
        time.sleep(10)
    else:
        raise RuntimeError('Timed out waiting for Render deployment.')

    if not live_ok(LIVE + '/'):
        raise RuntimeError('Deploy reported live, but public website verification failed.')
    if not live_ok(LIVE + '/app/login'):
        raise RuntimeError('Public website is live, but unified private /app/login verification failed.')
    print('\nLIVE VERIFIED OK')
    print('Website:', LIVE + '/')
    print('Partner System:', LIVE + '/app/')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nDEPLOYMENT STOPPED:', exc)
        sys.exit(1)
