from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app

ALLOWED_STATUSES = {"new", "read", "replied", "archived"}


def _database_url() -> str:
    return (current_app.config.get("DATABASE_URL") or "").strip()


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:///")


@contextmanager
def _connection() -> Iterator[Any]:
    url = _database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    if _is_sqlite(url):
        raw_path = url[len("sqlite:///") :]
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
        return

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - production dependency
        raise RuntimeError("PostgreSQL support is not installed.") from exc

    conn = psycopg.connect(url, connect_timeout=10, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_schema() -> None:
    url = _database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    if _is_sqlite(url):
        sql = """
        CREATE TABLE IF NOT EXISTS contact_inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new'
        )
        """
    else:
        sql = """
        CREATE TABLE IF NOT EXISTS contact_inquiries (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            name VARCHAR(100) NOT NULL,
            email VARCHAR(160) NOT NULL,
            company VARCHAR(140) NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'new'
        )
        """

    with _connection() as conn:
        conn.execute(sql)


def create_inquiry(record: dict[str, str]) -> int:
    ensure_schema()
    url = _database_url()
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        if _is_sqlite(url):
            cursor = conn.execute(
                """
                INSERT INTO contact_inquiries
                    (created_at, updated_at, name, email, company, message, status)
                VALUES (?, ?, ?, ?, ?, ?, 'new')
                """,
                (now, now, record["name"], record["email"], record.get("company", ""), record["message"]),
            )
            return int(cursor.lastrowid)

        row = conn.execute(
            """
            INSERT INTO contact_inquiries (name, email, company, message, status)
            VALUES (%s, %s, %s, %s, 'new')
            RETURNING id
            """,
            (record["name"], record["email"], record.get("company", ""), record["message"]),
        ).fetchone()
        return int(row["id"])


def _serialize(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key in ("created_at", "updated_at"):
        value = data.get(key)
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
    return data


def list_inquiries(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    ensure_schema()
    limit = max(1, min(int(limit), 200))
    url = _database_url()
    with _connection() as conn:
        if status in ALLOWED_STATUSES:
            if _is_sqlite(url):
                rows = conn.execute(
                    """
                    SELECT id, created_at, updated_at, name, email, company, message, status
                    FROM contact_inquiries WHERE status = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, created_at, updated_at, name, email, company, message, status
                    FROM contact_inquiries WHERE status = %s
                    ORDER BY id DESC LIMIT %s
                    """,
                    (status, limit),
                ).fetchall()
        else:
            if _is_sqlite(url):
                rows = conn.execute(
                    """
                    SELECT id, created_at, updated_at, name, email, company, message, status
                    FROM contact_inquiries ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, created_at, updated_at, name, email, company, message, status
                    FROM contact_inquiries ORDER BY id DESC LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
    return [_serialize(row) for row in rows]


def get_inquiry(inquiry_id: int) -> dict[str, Any] | None:
    ensure_schema()
    url = _database_url()
    with _connection() as conn:
        if _is_sqlite(url):
            row = conn.execute(
                "SELECT * FROM contact_inquiries WHERE id = ?", (int(inquiry_id),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM contact_inquiries WHERE id = %s", (int(inquiry_id),)
            ).fetchone()
    return _serialize(row) if row else None


def update_status(inquiry_id: int, status: str) -> dict[str, Any] | None:
    if status not in ALLOWED_STATUSES:
        raise ValueError("Invalid inquiry status.")
    ensure_schema()
    url = _database_url()
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        if _is_sqlite(url):
            conn.execute(
                "UPDATE contact_inquiries SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, int(inquiry_id)),
            )
        else:
            conn.execute(
                "UPDATE contact_inquiries SET status = %s, updated_at = NOW() WHERE id = %s",
                (status, int(inquiry_id)),
            )
    return get_inquiry(inquiry_id)


def counts() -> dict[str, int]:
    ensure_schema()
    data = {status: 0 for status in ALLOWED_STATUSES}
    with _connection() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS count FROM contact_inquiries GROUP BY status").fetchall()
    for row in rows:
        item = dict(row)
        if item.get("status") in data:
            data[item["status"]] = int(item["count"])
    data["total"] = sum(data.values())
    return data
