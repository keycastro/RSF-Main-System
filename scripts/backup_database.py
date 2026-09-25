"""Create a consistent SQLite recovery copy, including committed WAL pages."""
from __future__ import annotations

import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys


def database_path(folder: Path) -> Path:
    configured = os.environ.get('DATABASE_PATH')
    env_file = folder / '.env'
    if configured is None and env_file.exists():
        for raw in env_file.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = raw.strip().partition('=')
            if separator and key.strip() == 'DATABASE_PATH':
                configured = value.strip().strip('"').strip("'")
                break
    path = Path(configured) if configured else Path('instance/rsf_sales_partner.db')
    return path if path.is_absolute() else folder / path


def snapshot(folder: Path, destination: Path) -> dict:
    source = database_path(folder).resolve()
    if not source.exists():
        return {'database': str(source), 'snapshot': None}
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / 'rsf_sales_partner.db'
    # mode=ro prevents accidental creation of a missing operational database.
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
        with closing(sqlite3.connect(output)) as backup:
            original.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Database recovery copy failed integrity verification.')
    return {'database': str(source), 'snapshot': str(output)}


if __name__ == '__main__':
    print(json.dumps(snapshot(Path(sys.argv[1]), Path(sys.argv[2]))))
