from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask

from . import db as db_module

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    sql = None
    dict_row = None

MODE_ENV = "RSF_DATABASE_TRANSFER_MODE"
TARGET_ENV = "RSF_DATABASE_TRANSFER_TARGET_URL"
READ_ONLY_ENV = "RSF_DATABASE_TRANSFER_READ_ONLY"
MIGRATION_MARKER = "render_to_neon_migration_v1"


def _database_url(value: str, label: str) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError(f"{label} must be a PostgreSQL URL.")
    return value


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").lower()


def _connect(url: str):
    if psycopg is None:
        raise RuntimeError("PostgreSQL support is not installed.")
    return psycopg.connect(url, connect_timeout=20, row_factory=dict_row)


def _tables(conn) -> list[str]:
    rows = conn.execute(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema='public' AND table_type='BASE TABLE'
           ORDER BY table_name"""
    ).fetchall()
    return [str(row["table_name"]) for row in rows]


def _columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
        (table,),
    ).fetchall()
    return [str(row["column_name"]) for row in rows]


def _schema_version(conn) -> int | None:
    if "schema_migrations" not in _tables(conn):
        return None
    row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
    return int(row["version"]) if row and row["version"] is not None else None


def _counts(conn, tables: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for table in tables:
        row = conn.execute(
            sql.SQL("SELECT COUNT(*) AS n FROM {}").format(sql.Identifier(table))
        ).fetchone()
        result[table] = int(row["n"])
    return result


def _dependency_order(conn, tables: list[str]) -> list[str]:
    remaining = {table: set() for table in tables}
    rows = conn.execute(
        """SELECT tc.table_name AS child_table, ccu.table_name AS parent_table
           FROM information_schema.table_constraints tc
           JOIN information_schema.constraint_column_usage ccu
             ON ccu.constraint_name=tc.constraint_name
            AND ccu.constraint_schema=tc.constraint_schema
           WHERE tc.constraint_schema='public' AND tc.constraint_type='FOREIGN KEY'"""
    ).fetchall()
    for row in rows:
        child = str(row["child_table"])
        parent = str(row["parent_table"])
        if child in remaining and parent in remaining and child != parent:
            remaining[child].add(parent)
    order: list[str] = []
    while remaining:
        ready = sorted(t for t, deps in remaining.items() if not deps.intersection(remaining))
        if not ready:
            raise RuntimeError("Foreign-key cycle detected: " + ", ".join(sorted(remaining)))
        for table in ready:
            order.append(table)
            remaining.pop(table, None)
    return order


def _canonical(value) -> bytes:
    if value is None:
        return b"N"
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return b"B" + len(value).to_bytes(8, "big") + value
    if isinstance(value, bool):
        return b"T" if value else b"F"
    if isinstance(value, (datetime, date, time)):
        return b"D" + value.isoformat().encode("utf-8")
    if isinstance(value, Decimal):
        return b"M" + str(value).encode("utf-8")
    if isinstance(value, (dict, list)):
        return b"J" + json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return b"S" + str(value).encode("utf-8")


def _digest(conn, table: str, columns: list[str]) -> tuple[int, str]:
    if not columns:
        return 0, hashlib.sha256(b"").hexdigest()
    query = sql.SQL("SELECT {} FROM {}").format(
        sql.SQL(",").join(sql.Identifier(c) for c in columns),
        sql.Identifier(table),
    )
    cursor = conn.execute(query)
    aggregate = 0
    count = 0
    modulo = 1 << 256
    while True:
        batch = cursor.fetchmany(250)
        if not batch:
            break
        for row in batch:
            h = hashlib.sha256()
            for column in columns:
                payload = _canonical(row[column])
                h.update(len(payload).to_bytes(8, "big"))
                h.update(payload)
            aggregate = (aggregate + int.from_bytes(h.digest(), "big")) % modulo
            count += 1
    return count, f"{aggregate:064x}"


def _bootstrap_target_schema(app, target_url: str) -> None:
    target_app = Flask("rsf-database-transfer", root_path=app.root_path)
    target_app.config.update(
        TESTING=True,
        DATABASE_URL=target_url,
        DATABASE=str(Path(app.instance_path) / "transfer-unused.db"),
    )
    target_app.teardown_appcontext(db_module.close_db)
    with target_app.app_context():
        target_db = db_module.get_db()
        schema = (Path(target_app.root_path) / "schema.sql").read_text(encoding="utf-8")
        target_db.executescript(schema)
        target_db.execute(
            "INSERT OR IGNORE INTO schema_migrations(version,name) VALUES (?,?)",
            (1, "rsf-internal-sales-partner-v1"),
        )
        db_module._apply_migrations(target_db)
        target_db.commit()


def _copy_sequences(source, target, source_tables: set[str]) -> list[dict]:
    rows = source.execute(
        """SELECT tbl.relname AS table_name, att.attname AS column_name,
                  seq_ns.nspname AS sequence_schema, seq.relname AS sequence_name
           FROM pg_class seq
           JOIN pg_namespace seq_ns ON seq_ns.oid=seq.relnamespace
           JOIN pg_depend dep ON dep.objid=seq.oid AND dep.deptype IN ('a','i')
           JOIN pg_class tbl ON tbl.oid=dep.refobjid
           JOIN pg_namespace tbl_ns ON tbl_ns.oid=tbl.relnamespace
           JOIN pg_attribute att ON att.attrelid=tbl.oid AND att.attnum=dep.refobjsubid
           WHERE seq.relkind='S' AND seq_ns.nspname='public' AND tbl_ns.nspname='public'
           ORDER BY tbl.relname,att.attname"""
    ).fetchall()
    result = []
    for row in rows:
        table = str(row["table_name"])
        if table not in source_tables:
            continue
        schema = str(row["sequence_schema"])
        name = str(row["sequence_name"])
        state = source.execute(
            sql.SQL("SELECT last_value,is_called FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(name)
            )
        ).fetchone()
        target.execute(
            "SELECT setval(%s::regclass,%s,%s)",
            (f'"{schema}"."{name}"', int(state["last_value"]), bool(state["is_called"])),
        )
        result.append({
            "table": table,
            "column": str(row["column_name"]),
            "sequence": f"{schema}.{name}",
            "last_value": int(state["last_value"]),
            "is_called": bool(state["is_called"]),
        })
    return result


def audit_transfer(app) -> dict:
    source_url = _database_url(app.config.get("DATABASE_URL", ""), "Source DATABASE_URL")
    target_url = _database_url(os.environ.get(TARGET_ENV, ""), TARGET_ENV)
    if source_url == target_url:
        raise RuntimeError("Source and target database URLs are identical.")
    if not _host(target_url).endswith(".neon.tech"):
        raise RuntimeError("Target host is not Neon PostgreSQL.")
    with _connect(source_url) as source, _connect(target_url) as target:
        source.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        source_tables = _tables(source)
        result = {
            "mode": "audit",
            "source_host": _host(source_url),
            "target_host": _host(target_url),
            "source_schema_version": _schema_version(source),
            "target_schema_version": _schema_version(target),
            "source_tables": source_tables,
            "target_tables": _tables(target),
            "source_row_counts": _counts(source, source_tables),
        }
        source.rollback()
        return result


def migrate_transfer(app) -> dict:
    source_url = _database_url(app.config.get("DATABASE_URL", ""), "Source DATABASE_URL")
    target_url = _database_url(os.environ.get(TARGET_ENV, ""), TARGET_ENV)
    if source_url == target_url:
        raise RuntimeError("Source and target database URLs are identical.")
    if not _host(target_url).endswith(".neon.tech"):
        raise RuntimeError("Target host is not Neon PostgreSQL.")

    _bootstrap_target_schema(app, target_url)
    with _connect(source_url) as source, _connect(target_url) as target:
        source.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        source_tables = _tables(source)
        target_tables = _tables(target)
        source_only = sorted(set(source_tables) - set(target_tables))
        if source_only:
            raise RuntimeError(
                "Target schema is missing source tables; refusing partial migration: " + ", ".join(source_only)
            )
        source_version = _schema_version(source)
        target_version = _schema_version(target)
        if source_version != target_version:
            raise RuntimeError(
                f"Schema version mismatch: source={source_version!r}, target={target_version!r}"
            )

        order = _dependency_order(source, source_tables)
        if source_tables:
            target.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(",").join(sql.Identifier(t) for t in source_tables)
                )
            )

        table_report: dict[str, dict] = {}
        for table in order:
            source_columns = _columns(source, table)
            target_columns = _columns(target, table)
            missing = [c for c in source_columns if c not in target_columns]
            if missing:
                raise RuntimeError(f"Target table {table} is missing columns: {', '.join(missing)}")
            select_query = sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(",").join(sql.Identifier(c) for c in source_columns),
                sql.Identifier(table),
            )
            insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(",").join(sql.Identifier(c) for c in source_columns),
                sql.SQL(",").join(sql.Placeholder() for _ in source_columns),
            )
            cursor = source.execute(select_query)
            copied = 0
            while True:
                batch = cursor.fetchmany(250)
                if not batch:
                    break
                target.executemany(
                    insert_query,
                    [tuple(row[c] for c in source_columns) for row in batch],
                )
                copied += len(batch)
            table_report[table] = {"rows_copied": copied, "columns": source_columns}

        sequence_report = _copy_sequences(source, target, set(source_tables))
        target.commit()

        verification: dict[str, dict] = {}
        for table in source_tables:
            columns = table_report[table]["columns"]
            source_count, source_digest = _digest(source, table, columns)
            target_count, target_digest = _digest(target, table, columns)
            verification[table] = {
                "source_count": source_count,
                "target_count": target_count,
                "digest_match": source_digest == target_digest,
            }
            if source_count != target_count or source_digest != target_digest:
                raise RuntimeError(f"Verification failed for table {table}.")

        completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        target.execute(
            """INSERT INTO settings(key,value,updated_at) VALUES (%s,%s,%s)
               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at""",
            (
                MIGRATION_MARKER,
                json.dumps({
                    "completed_at": completed_at,
                    "source_host": _host(source_url),
                    "target_host": _host(target_url),
                    "schema_version": target_version,
                    "table_count": len(source_tables),
                }, sort_keys=True),
                completed_at,
            ),
        )
        target.commit()
        source.rollback()
        return {
            "mode": "migrate",
            "source_host": _host(source_url),
            "target_host": _host(target_url),
            "source_schema_version": source_version,
            "target_schema_version": target_version,
            "tables": table_report,
            "sequences": sequence_report,
            "verification": verification,
        }


def run_if_requested(app) -> None:
    mode = (os.environ.get(MODE_ENV) or "").strip().lower()
    if not mode:
        return
    if mode not in {"audit", "migrate"}:
        raise RuntimeError(f"Unsupported {MODE_ENV}: {mode!r}")
    if mode == "migrate" and (os.environ.get(READ_ONLY_ENV) or "").strip() != "1":
        raise RuntimeError(f"{READ_ONLY_ENV}=1 is required for migration mode.")
    report = audit_transfer(app) if mode == "audit" else migrate_transfer(app)
    app.logger.warning("RSF_DATABASE_TRANSFER_RESULT %s", json.dumps(report, sort_keys=True, default=str))
