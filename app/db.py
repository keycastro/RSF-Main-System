from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import io
import zipfile
from pathlib import Path
from flask import current_app, g

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg import IntegrityError as PGIntegrityError, OperationalError as PGOperationalError
except Exception:  # local install can still bootstrap SQLite before production deps are present
    psycopg = None
    dict_row = None
    class PGIntegrityError(Exception):
        pass
    class PGOperationalError(Exception):
        pass

IntegrityError = PGIntegrityError
OperationalError = PGOperationalError

SCHEMA_VERSION = 26
SCHEMA_NAME = "rsf-main-system-v1.18.63-prospect-deal-notes-sync"
SERIAL_ID_TABLES = {"users","commission_stages","partners","leads","lead_notes","followups","sales","commissions","sale_corrections","resources","duplicate_claims","activity_log","messages","message_attachments","voice_calls","voice_call_signals","website_inquiries","client_conversations","client_messages","client_attachments","client_notifications","prospects","deals","deal_documents"}


def using_postgres() -> bool:
    url = (current_app.config.get("DATABASE_URL") or "").strip()
    return url.startswith(("postgres://", "postgresql://"))


def _qmark_to_percent(sql: str) -> str:
    # The application SQL does not place question-mark placeholders inside SQL string literals.
    return sql.replace("?", "%s")


def _translate_sql(sql: str) -> str:
    stripped = sql.strip()
    upper = stripped.upper()
    if upper == "BEGIN IMMEDIATE":
        return "BEGIN"
    if upper.startswith("PRAGMA "):
        return stripped
    sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, flags=re.I)
    if re.match(r"^\s*INSERT\s+INTO\b", sql, flags=re.I) and "OR IGNORE" not in upper:
        # Marker added below only for statements originally using OR IGNORE.
        pass
    return _qmark_to_percent(sql)


class _PGResult:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
    def fetchone(self):
        return self._cursor.fetchone()
    def fetchall(self):
        return self._cursor.fetchall()
    @property
    def rowcount(self):
        return self._cursor.rowcount
    def __iter__(self):
        return iter(self._cursor)


class _PGConnection:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        stripped = sql.strip()
        upper = stripped.upper()
        if upper.startswith("PRAGMA TABLE_INFO("):
            table = stripped[stripped.find("(")+1:stripped.rfind(")")].strip().strip('"\'')
            cur = self._conn.cursor(row_factory=dict_row)
            cur.execute(
                "SELECT column_name AS name, data_type AS type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                (table,),
            )
            return _PGResult(cur)
        if upper.startswith("PRAGMA "):
            cur = self._conn.cursor(row_factory=dict_row)
            cur.execute("SELECT 1 AS ok")
            return _PGResult(cur)
        if upper == "BEGIN IMMEDIATE":
            sql = "BEGIN"
        original_ignore = bool(re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", sql, flags=re.I))
        translated = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, flags=re.I)
        translated = re.sub(r"\bBLOB\b", "BYTEA", translated, flags=re.I)
        translated = _qmark_to_percent(translated)
        if original_ignore:
            translated = translated.rstrip().rstrip(';') + " ON CONFLICT DO NOTHING"
        cur = self._conn.cursor(row_factory=dict_row)
        cur.execute(translated, params or ())
        lastrowid = None
        match = re.match(r'^\s*INSERT\s+INTO\s+["\']?([A-Za-z_][A-Za-z0-9_]*)', translated, flags=re.I)
        table_name = match.group(1) if match else ""
        if table_name in SERIAL_ID_TABLES and not original_ignore and cur.rowcount and cur.rowcount > 0:
            seq_cur = self._conn.cursor(row_factory=dict_row)
            seq_cur.execute("SELECT LASTVAL() AS id")
            row = seq_cur.fetchone()
            if row:
                lastrowid = int(row["id"])
        return _PGResult(cur, lastrowid)

    def executemany(self, sql, seq):
        original_ignore = bool(re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", sql, flags=re.I))
        translated = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, flags=re.I)
        translated = _qmark_to_percent(translated)
        if original_ignore:
            translated = translated.rstrip().rstrip(';') + " ON CONFLICT DO NOTHING"
        cur = self._conn.cursor(row_factory=dict_row)
        cur.executemany(translated, list(seq))
        return _PGResult(cur)

    def executescript(self, script: str):
        script = re.sub(r"^\s*PRAGMA\s+[^;]+;", "", script, flags=re.I | re.M)
        script = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        script = script.replace(" COLLATE NOCASE", "")
        # CREATE statements in this schema contain no semicolons inside string literals.
        cur = None
        for statement in [part.strip() for part in script.split(';') if part.strip()]:
            cur = self.execute(statement)
        return cur

    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        self._conn.close()


def get_db():
    if "db" not in g:
        if using_postgres():
            if psycopg is None:
                raise RuntimeError("PostgreSQL support is not installed.")
            url = current_app.config["DATABASE_URL"]
            conn = psycopg.connect(url, connect_timeout=15, row_factory=dict_row)
            g.db = _PGConnection(conn)
        else:
            path = Path(current_app.config["DATABASE"])
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA journal_mode=WAL")
            g.db = conn
    return g.db


def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _schema_table_ddl(table: str) -> str:
    """Return this release's CREATE TABLE statement for a known application table."""
    schema = (Path(current_app.root_path) / "schema.sql").read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\(.*?\n\);",
        schema,
        flags=re.S | re.I,
    )
    if not match:
        raise RuntimeError(f"Schema definition not found for {table}.")
    return match.group(0)


def _sqlite_rebuild_table_from_release_schema(db: sqlite3.Connection, table: str) -> None:
    """Rebuild one SQLite table while preserving every existing row.

    SQLite cannot drop NOT NULL or change a foreign-key action in place. The release
    schema is therefore used to create a temporary replacement, copy all common
    columns by name, and atomically restore the original table name while foreign-key
    enforcement is temporarily disabled by the caller.
    """
    temp = f"__rsf_v13_{table}"
    db.execute(f'DROP TABLE IF EXISTS "{temp}"')
    ddl = _schema_table_ddl(table)
    ddl = re.sub(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}",
        f'CREATE TABLE "{temp}"',
        ddl,
        count=1,
        flags=re.I,
    )
    db.execute(ddl)
    old_columns = [row["name"] for row in db.execute(f'PRAGMA table_info("{table}")').fetchall()]
    new_columns = [row["name"] for row in db.execute(f'PRAGMA table_info("{temp}")').fetchall()]
    common = [name for name in old_columns if name in new_columns]
    if not common:
        raise RuntimeError(f"No common columns found while migrating {table}.")
    quoted = ",".join(f'"{name}"' for name in common)
    db.execute(f'INSERT INTO "{temp}" ({quoted}) SELECT {quoted} FROM "{table}"')
    db.execute(f'DROP TABLE "{table}"')
    db.execute(f'ALTER TABLE "{temp}" RENAME TO "{table}"')


def _sqlite_rebuild_partner_account_constraints(db: sqlite3.Connection) -> None:
    """Make Partner-account identity references nullable without losing history."""
    tables = (
        "partners", "leads", "lead_notes", "followups", "sales", "resources",
        "messages", "voice_calls", "voice_call_signals",
    )
    db.commit()
    db.execute("PRAGMA foreign_keys=OFF")
    try:
        for table in tables:
            _sqlite_rebuild_table_from_release_schema(db, table)
        # Re-create all normal release indexes dropped with the rebuilt tables.
        schema = (Path(current_app.root_path) / "schema.sql").read_text(encoding="utf-8")
        for statement in re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS .*?;", schema, flags=re.I):
            db.execute(statement)
        # V6 intentionally allows only one open private voice call across RSF.
        db.execute("DROP INDEX IF EXISTS uq_voice_calls_open_partner")
        db.execute("DROP INDEX IF EXISTS uq_voice_calls_single_open")
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_voice_calls_single_open "
            "ON voice_calls((1)) WHERE status IN ('RINGING','ACTIVE')"
        )
        db.execute(
            """UPDATE partners
               SET historical_name=COALESCE(
                   (SELECT u.full_name FROM users u WHERE u.id=partners.user_id),
                   historical_name,
                   ''
               )"""
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys=ON")
    violations = db.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"Partner-account migration created foreign-key violations: {violations[:5]}")


def _postgres_fk_name(db, table: str, column: str) -> str | None:
    row = db.execute(
        """SELECT tc.constraint_name
           FROM information_schema.table_constraints tc
           JOIN information_schema.key_column_usage kcu
             ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
           WHERE tc.table_schema='public' AND tc.table_name=?
             AND tc.constraint_type='FOREIGN KEY' AND kcu.column_name=?
           LIMIT 1""",
        (table, column),
    ).fetchone()
    return row["constraint_name"] if row else None


def _postgres_make_user_reference_nullable(db, table: str, column: str, *, target_table: str = "users") -> None:
    allowed_tables = {
        "partners", "leads", "lead_notes", "followups", "sales", "resources",
        "messages", "voice_calls", "voice_call_signals",
    }
    allowed_columns = {
        "user_id", "created_by_user_id", "author_user_id", "sender_user_id", "started_by_user_id",
    }
    if table not in allowed_tables or column not in allowed_columns:
        raise RuntimeError("Unsafe Partner-account migration identifier.")
    db.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP NOT NULL')
    constraint = _postgres_fk_name(db, table, column)
    if constraint:
        safe_constraint = constraint.replace('"', '""')
        db.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{safe_constraint}"')
    constraint_name = f"{table}_{column}_fkey"
    db.execute(
        f'ALTER TABLE "{table}" ADD CONSTRAINT "{constraint_name}" '
        f'FOREIGN KEY ("{column}") REFERENCES "{target_table}"(id) ON DELETE SET NULL'
    )


def _apply_migrations(db: sqlite3.Connection) -> None:
    applied = {row["version"] for row in db.execute("SELECT version FROM schema_migrations").fetchall()}

    # V2 removes single-field UNIQUE lead constraints. Duplicate ownership is now
    # decided by the multi-signal matching service instead of one email/phone/domain.
    if 2 not in applied:
        db.executescript(
            """
            DROP INDEX IF EXISTS uq_lead_email_norm;
            DROP INDEX IF EXISTS uq_lead_phone_norm;
            DROP INDEX IF EXISTS uq_lead_domain;
            DROP INDEX IF EXISTS uq_lead_company_contact;
            CREATE INDEX IF NOT EXISTS idx_lead_email_norm ON leads(email_norm) WHERE email_norm <> '';
            CREATE INDEX IF NOT EXISTS idx_lead_phone_norm ON leads(phone_norm) WHERE phone_norm <> '';
            CREATE INDEX IF NOT EXISTS idx_lead_domain ON leads(website_domain) WHERE website_domain <> '';
            CREATE INDEX IF NOT EXISTS idx_lead_company_contact ON leads(company_norm, contact_norm) WHERE company_norm <> '' AND contact_norm <> '';
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (2, "rsf-partner-system-v1.1-duplicate-indexes"),
        )

    # V3 moves the legacy lead summary field into authored lead notes. This gives
    # notes clear ownership so a reassigned lead cannot expose the previous
    # partner's private note to the new partner. Founder still retains full history.
    if 3 not in applied:
        db.execute(
            """INSERT INTO lead_notes(lead_id,author_user_id,body,created_at)
               SELECT id,created_by_user_id,summary_notes,registered_at FROM leads
               WHERE trim(summary_notes) <> ''"""
        )
        db.execute("UPDATE leads SET summary_notes='' WHERE trim(summary_notes) <> ''")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (3, "rsf-partner-system-v1.1-private-notes"),
        )

    # V4 makes partner passwords Founder-managed. Partners no longer have a
    # self-service password-change flow, so clear any legacy first-login flags
    # that could otherwise lock an older partner account on the profile page.
    if 4 not in applied:
        db.execute("UPDATE users SET force_password_change=0")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (4, "rsf-partner-system-v1.1-founder-managed-partner-passwords"),
        )

    # V5 adds private Founder <-> Partner messages and browser voice-call signaling.
    # Every row is tied to exactly one partner. Partner routes enforce that a
    # partner can access only their own conversation.
    if 5 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
                sender_user_id INTEGER NOT NULL REFERENCES users(id),
                body TEXT NOT NULL,
                founder_read_at TEXT,
                partner_read_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_partner ON messages(partner_id, id);
            CREATE INDEX IF NOT EXISTS idx_messages_founder_unread ON messages(founder_read_at, partner_id) WHERE founder_read_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_messages_partner_unread ON messages(partner_read_at, partner_id) WHERE partner_read_at IS NULL;

            CREATE TABLE IF NOT EXISTS voice_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
                started_by_user_id INTEGER NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'RINGING' CHECK (status IN ('RINGING','ACTIVE','ENDED','DECLINED','MISSED')),
                started_at TEXT NOT NULL,
                answered_at TEXT,
                ended_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_voice_calls_partner_status ON voice_calls(partner_id, status, id DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_voice_calls_open_partner ON voice_calls(partner_id) WHERE status IN ('RINGING','ACTIVE');

            CREATE TABLE IF NOT EXISTS voice_call_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
                sender_user_id INTEGER NOT NULL REFERENCES users(id),
                kind TEXT NOT NULL CHECK (kind IN ('OFFER','ANSWER','ICE')),
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_voice_call_signals_call ON voice_call_signals(call_id, id);
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (5, "rsf-partner-system-v1.1-private-messaging-voice"),
        )

    # V6 simplifies and hardens private voice calling. It keeps one Founder call
    # open at a time, records simple end reasons, and tracks both participants so
    # stale browser sessions can be cleaned up without exposing technical details.
    if 6 not in applied:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(voice_calls)").fetchall()}
        if "end_reason" not in columns:
            db.execute("ALTER TABLE voice_calls ADD COLUMN end_reason TEXT")
        if "ended_by_user_id" not in columns:
            db.execute("ALTER TABLE voice_calls ADD COLUMN ended_by_user_id INTEGER REFERENCES users(id)")
        if "caller_seen_at" not in columns:
            db.execute("ALTER TABLE voice_calls ADD COLUMN caller_seen_at TEXT")
        if "receiver_seen_at" not in columns:
            db.execute("ALTER TABLE voice_calls ADD COLUMN receiver_seen_at TEXT")

        # Older builds allowed one open call per partner. RSF has one Founder, so
        # keep only the newest open call before enforcing one private call globally.
        open_rows = db.execute(
            "SELECT id,status FROM voice_calls WHERE status IN ('RINGING','ACTIVE') ORDER BY id DESC"
        ).fetchall()
        if len(open_rows) > 1:
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat()
            for row in open_rows[1:]:
                status = "MISSED" if row["status"] == "RINGING" else "ENDED"
                reason = "missed" if row["status"] == "RINGING" else "connection_lost"
                db.execute(
                    "UPDATE voice_calls SET status=?,end_reason=?,ended_at=? WHERE id=?",
                    (status, reason, now, row["id"]),
                )
        db.execute("DROP INDEX IF EXISTS uq_voice_calls_single_open")
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_voice_calls_single_open ON voice_calls((1)) WHERE status IN ('RINGING','ACTIVE')"
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (6, "rsf-partner-system-v1.1-simple-private-voice"),
        )

    # V7 adds protected message attachments while preserving the existing
    # Founder <-> Partner conversation model. Files are stored outside static
    # assets and can only be served after normal conversation authorization.
    if 7 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS message_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_message_attachments_message ON message_attachments(message_id, id);
            CREATE INDEX IF NOT EXISTS idx_message_attachments_partner ON message_attachments(partner_id, id);
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (7, "rsf-partner-system-v1.1-compact-private-messages"),
        )

    # V8 adds one private profile-picture reference per user. Uploaded pictures
    # remain outside static assets and are served only through an authenticated route.
    if 8 not in applied:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
        if "avatar_stored_name" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN avatar_stored_name TEXT")
        if "avatar_mime_type" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN avatar_mime_type TEXT")
        if "avatar_updated_at" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN avatar_updated_at TEXT")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (8, "rsf-partner-system-v1.1-user-profile-pictures"),
        )

    # V9 unifies the public RSF website intake with the private Partner System.
    # Inquiries are shared only while unclaimed; claimed client conversations are
    # visible only to the current owner and Founder. Internal Founder/Partner
    # messages remain in their existing separate tables.
    if 9 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS website_inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                email_norm TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'UNCLAIMED' CHECK (status IN ('UNCLAIMED','CLAIMED','ARCHIVED','SPAM')),
                claimed_by_partner_id INTEGER REFERENCES partners(id),
                claimed_at TEXT,
                lead_id INTEGER REFERENCES leads(id),
                client_conversation_id INTEGER,
                source_type TEXT NOT NULL DEFAULT '',
                source_slug TEXT NOT NULL DEFAULT '',
                source_title TEXT NOT NULL DEFAULT '',
                source_action TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_website_inquiries_queue ON website_inquiries(status,created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_website_inquiries_owner ON website_inquiries(claimed_by_partner_id,status,updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_website_inquiries_email ON website_inquiries(email_norm,created_at DESC);

            CREATE TABLE IF NOT EXISTS client_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inquiry_id INTEGER REFERENCES website_inquiries(id),
                lead_id INTEGER REFERENCES leads(id),
                owner_partner_id INTEGER REFERENCES partners(id),
                client_name TEXT NOT NULL,
                client_email TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','CLOSED')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_client_conversations_owner ON client_conversations(owner_partner_id,status,updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_client_conversations_lead ON client_conversations(lead_id,updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_client_conversations_email ON client_conversations(client_email,status,updated_at DESC);

            CREATE TABLE IF NOT EXISTS client_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES client_conversations(id) ON DELETE CASCADE,
                direction TEXT NOT NULL CHECK (direction IN ('INBOUND','OUTBOUND')),
                channel TEXT NOT NULL CHECK (channel IN ('WEBSITE','EMAIL')),
                sender_email TEXT NOT NULL DEFAULT '',
                recipient_email TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                sent_by_user_id INTEGER REFERENCES users(id),
                external_message_id TEXT NOT NULL DEFAULT '',
                in_reply_to TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_client_messages_conversation ON client_messages(conversation_id,id);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_client_messages_external_id ON client_messages(external_message_id) WHERE external_message_id <> '';
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (9, "rsf-unified-system-v1.2-client-inbox"),
        )

    # V10 hardens the unified client workflow: automatic email processing state,
    # response accountability, client attachments, and per-user notifications.
    if 10 not in applied:
        conversation_columns = {row["name"] for row in db.execute("PRAGMA table_info(client_conversations)").fetchall()}
        for name, ddl in [
            ("first_response_due_at", "TEXT"),
            ("first_responded_at", "TEXT"),
            ("last_client_message_at", "TEXT"),
            ("last_outbound_message_at", "TEXT"),
        ]:
            if name not in conversation_columns:
                db.execute(f"ALTER TABLE client_conversations ADD COLUMN {name} {ddl}")

        message_columns = {row["name"] for row in db.execute("PRAGMA table_info(client_messages)").fetchall()}
        if "delivery_status" not in message_columns:
            db.execute("ALTER TABLE client_messages ADD COLUMN delivery_status TEXT NOT NULL DEFAULT ''")
        if "delivery_error" not in message_columns:
            db.execute("ALTER TABLE client_messages ADD COLUMN delivery_error TEXT NOT NULL DEFAULT ''")

        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS client_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL REFERENCES client_messages(id) ON DELETE CASCADE,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_client_attachments_message ON client_attachments(message_id,id);

            CREATE TABLE IF NOT EXISTS client_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id INTEGER,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                read_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_client_notifications_user_unread ON client_notifications(user_id,read_at,id DESC);
            CREATE INDEX IF NOT EXISTS idx_client_notifications_entity ON client_notifications(entity_type,entity_id,id DESC);

            CREATE TABLE IF NOT EXISTS background_leases (
                name TEXT PRIMARY KEY,
                holder TEXT NOT NULL,
                lease_until TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (10, "rsf-unified-system-v1.3-operations-hardening"),
        )

    # V11 stores protected uploads in the database when running online so Render
    # restarts/deploys cannot erase profile pictures or message/client attachments.
    if 11 not in applied:
        user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
        if "avatar_data" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN avatar_data BLOB")
        attachment_columns = {row["name"] for row in db.execute("PRAGMA table_info(message_attachments)").fetchall()}
        if "data_blob" not in attachment_columns:
            db.execute("ALTER TABLE message_attachments ADD COLUMN data_blob BLOB")
        client_attachment_columns = {row["name"] for row in db.execute("PRAGMA table_info(client_attachments)").fetchall()}
        if "data_blob" not in client_attachment_columns:
            db.execute("ALTER TABLE client_attachments ADD COLUMN data_blob BLOB")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (11, "rsf-unified-system-v1.5.1-database-file-storage"),
        )

    # V12 removes the old deactivate/reactivate account lifecycle. Existing Partner
    # accounts are restored to normal access, while permanent deletion is tracked
    # separately so business history can keep its original Partner IDs safely.
    if 12 not in applied:
        partner_columns = {row["name"] for row in db.execute("PRAGMA table_info(partners)").fetchall()}
        if "account_deleted_at" not in partner_columns:
            db.execute("ALTER TABLE partners ADD COLUMN account_deleted_at TEXT")
        db.execute("UPDATE partners SET active=1 WHERE account_deleted_at IS NULL")
        db.execute(
            "UPDATE users SET active=1 WHERE role='partner' AND id IN (SELECT user_id FROM partners WHERE account_deleted_at IS NULL)"
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (12, "rsf-main-system-v1.9.0-partner-account-lifecycle"),
        )

    # V13 makes Delete a real account deletion instead of a disabled/tombstoned
    # login. The Partner row becomes a scrubbed historical attribution record so
    # leads, sales, commissions, messages and other company history keep their
    # original Partner ID without retaining an authentication account/profile.
    if 13 not in applied:
        if using_postgres():
            partner_columns = {row["name"] for row in db.execute("PRAGMA table_info(partners)").fetchall()}
            if "historical_name" not in partner_columns:
                db.execute("ALTER TABLE partners ADD COLUMN historical_name TEXT NOT NULL DEFAULT ''")
            db.execute(
                """UPDATE partners p SET historical_name=u.full_name
                   FROM users u WHERE p.user_id=u.id AND trim(p.historical_name)=''"""
            )
            for table, column in (
                ("partners", "user_id"),
                ("leads", "created_by_user_id"),
                ("lead_notes", "author_user_id"),
                ("followups", "created_by_user_id"),
                ("sales", "created_by_user_id"),
                ("resources", "created_by_user_id"),
                ("messages", "sender_user_id"),
                ("voice_calls", "started_by_user_id"),
                ("voice_call_signals", "sender_user_id"),
            ):
                _postgres_make_user_reference_nullable(db, table, column)
        else:
            _sqlite_rebuild_partner_account_constraints(db)
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (13, "rsf-main-system-v1.9.0-hard-partner-account-delete"),
        )

    # V14 adds a Founder-only encrypted credential vault. Authentication continues
    # to use password_hash; this table exists only so the authenticated Founder can
    # explicitly reveal/copy the current Founder and Partner passwords.
    if 14 not in applied:
        db.execute(
            """CREATE TABLE IF NOT EXISTS account_password_vault (
                   user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                   encrypted_password TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )"""
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (14, "rsf-v1.9.4-founder-account-password-visibility"),
        )

    # V15 adds append-only sale/commission correction history. Approved or paid
    # commission rows stay unchanged; later refunds and revenue corrections are
    # recorded separately so financial history remains auditable.
    if 15 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sale_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL REFERENCES sales(id),
                commission_id INTEGER NOT NULL REFERENCES commissions(id),
                kind TEXT NOT NULL CHECK (kind IN ('REFUND','CHARGEBACK','REVENUE_CORRECTION','SALE_ADJUSTMENT','COMMISSION_CORRECTION')),
                old_deal_cents INTEGER NOT NULL CHECK (old_deal_cents >= 0),
                new_deal_cents INTEGER NOT NULL CHECK (new_deal_cents >= 0),
                old_invoiced_cents INTEGER NOT NULL CHECK (old_invoiced_cents >= 0),
                new_invoiced_cents INTEGER NOT NULL CHECK (new_invoiced_cents >= 0),
                old_collected_cents INTEGER NOT NULL CHECK (old_collected_cents >= 0),
                new_collected_cents INTEGER NOT NULL CHECK (new_collected_cents >= 0),
                old_qualifying_cents INTEGER NOT NULL CHECK (old_qualifying_cents >= 0),
                new_qualifying_cents INTEGER NOT NULL CHECK (new_qualifying_cents >= 0),
                commission_change_cents INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sale_corrections_sale ON sale_corrections(sale_id,id);
            CREATE INDEX IF NOT EXISTS idx_sale_corrections_commission ON sale_corrections(commission_id,id);
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (15, "rsf-v1.10.1-sale-correction-history"),
        )

    # V16 makes the existing user Name the private-workspace login ID.
    # Existing emails stay untouched as legacy data, but authentication no longer uses them.
    if 16 not in applied:
        blank = db.execute(
            "SELECT id FROM users WHERE active=1 AND trim(COALESCE(full_name,''))='' LIMIT 1"
        ).fetchone()
        if blank:
            raise RuntimeError(
                "Name login update stopped: an active account has no Name. Add a unique Name before updating."
            )
        duplicate = db.execute(
            """SELECT lower(trim(full_name)) login_name,COUNT(*) account_count
               FROM users WHERE active=1
               GROUP BY lower(trim(full_name)) HAVING COUNT(*)>1 LIMIT 1"""
        ).fetchone()
        if duplicate:
            raise RuntimeError(
                "Name login update stopped: two active accounts use the same Name. Rename one account before updating."
            )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_active_login_name "
            "ON users(lower(trim(full_name))) WHERE active=1"
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (16, "rsf-v1.11.0-name-password-login"),
        )


    # V17 adds the shared Prospects work queue documented in the RSF workflow.
    # New prospects start as NOT_CONTACTED. The same record carries forward while
    # it remains NOT_CONTACTED or NO_ANSWER; no daily duplicate row is created.
    if 17 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_norm TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NOT_CONTACTED',
                recorded_date TEXT NOT NULL,
                created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_prospects_name_norm ON prospects(name_norm);
            CREATE INDEX IF NOT EXISTS idx_prospects_daily_queue ON prospects(recorded_date,status,id);
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (17, "rsf-v1.13.0-prospects-work-queue"),
        )

    # V18 adds the approved Prospect research fields while preserving all existing rows.
    # The legacy internal name column remains the Company identity and duplicate key.
    if 18 not in applied:
        existing = {row["name"] for row in db.execute("PRAGMA table_info(prospects)").fetchall()}
        prospect_fields = (
            "business_type",
            "problem",
            "platform_wanted",
            "post_link",
            "post_date",
            "system_wanted",
            "budget",
            "location",
            "website",
            "contact",
            "email",
            "phone",
        )
        for column in prospect_fields:
            if column not in existing:
                db.execute(f'ALTER TABLE prospects ADD COLUMN "{column}" TEXT NOT NULL DEFAULT \'\'')
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (18, "rsf-v1.15.0-approved-prospect-fields"),
        )

    # V19 adds the approved Contact Attempt counter to every Prospect.
    # Existing Prospect records start at zero and are preserved.
    if 19 not in applied:
        existing = {row["name"] for row in db.execute("PRAGMA table_info(prospects)").fetchall()}
        if "contact_attempt" not in existing:
            db.execute("ALTER TABLE prospects ADD COLUMN contact_attempt INTEGER NOT NULL DEFAULT 0")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (19, "rsf-v1.15.5-prospect-inline-edit-contact-attempt"),
        )

    # V20 adds the approved Deals workflow. A Deal links to one existing Prospect;
    # the original Prospect row stays intact and Company is not duplicated in Deals.
    if 20 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL UNIQUE REFERENCES prospects(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'DEAL' CHECK (status IN ('DEAL','DEMO','PROPOSAL','DECISION','WON','LOST')),
                demo_date TEXT NOT NULL DEFAULT '',
                followup_date TEXT NOT NULL DEFAULT '',
                next_step TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT '',
                contact_number TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                notes_after_conversation TEXT NOT NULL DEFAULT '',
                created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_deals_status_updated ON deals(status,updated_at DESC,id DESC);
            CREATE INDEX IF NOT EXISTS idx_deals_followup ON deals(followup_date,status,id);
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (20, "rsf-v1.16.0-linked-deals-workflow"),
        )

    # V21 renames the Deal workflow field from Stage to Status while preserving
    # any existing Deal rows created by v1.16.0.
    if 21 not in applied:
        deal_columns = {row["name"] for row in db.execute("PRAGMA table_info(deals)").fetchall()}
        if "stage" in deal_columns and "status" not in deal_columns:
            db.execute("ALTER TABLE deals RENAME COLUMN stage TO status")
        db.execute("DROP INDEX IF EXISTS idx_deals_stage_updated")
        db.execute("DROP INDEX IF EXISTS idx_deals_status_updated")
        db.execute("DROP INDEX IF EXISTS idx_deals_followup")
        db.execute("CREATE INDEX IF NOT EXISTS idx_deals_status_updated ON deals(status,updated_at DESC,id DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_deals_followup ON deals(followup_date,status,id)")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (21, "rsf-v1.16.1-deal-prospect-deal-status"),
        )

    # V22 adds persistent, Deal-linked document storage. Files are stored in the
    # database so production deploys/restarts do not erase signed agreements,
    # proposals, invoices, requirements, approvals, or other Deal documents.
    if 22 not in applied:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS deal_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                document_type TEXT NOT NULL,
                display_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
                data_blob BLOB NOT NULL,
                uploaded_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_deal_documents_deal ON deal_documents(deal_id,created_at DESC,id DESC);
            """
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (22, "rsf-v1.17.0-deal-documents"),
        )

    # V23 renames the real shared Prospect/Deal workflow status from INTERESTED
    # to DEAL. Existing records are migrated, and the Deal column default/CHECK
    # is rebuilt so the database, backend, UI, and future code all use DEAL.
    if 23 not in applied:
        if using_postgres():
            check_rows = db.execute(
                """SELECT con.conname AS name
                   FROM pg_constraint con
                   JOIN pg_class rel ON rel.oid=con.conrelid
                   JOIN pg_namespace nsp ON nsp.oid=rel.relnamespace
                   WHERE nsp.nspname='public'
                     AND rel.relname='deals'
                     AND con.contype='c'
                     AND position('status' in lower(pg_get_constraintdef(con.oid))) > 0"""
            ).fetchall()
            for row in check_rows:
                constraint_name = str(row["name"]).replace('"', '""')
                db.execute(f'ALTER TABLE deals DROP CONSTRAINT "{constraint_name}"')

            db.execute("ALTER TABLE deals ALTER COLUMN status SET DEFAULT 'DEAL'")
            db.execute("UPDATE deals SET status='DEAL' WHERE status='INTERESTED'")
            db.execute("UPDATE prospects SET status='DEAL' WHERE status='INTERESTED'")
            db.execute(
                """ALTER TABLE deals
                   ADD CONSTRAINT deals_status_check
                   CHECK (status IN ('DEAL','DEMO','PROPOSAL','DECISION','WON','LOST'))"""
            )
        else:
            # SQLite cannot change a CHECK constraint in place. Rebuild only the
            # deals table from the release schema while preserving every row.
            db.commit()
            db.execute("PRAGMA foreign_keys=OFF")
            try:
                temp = "__rsf_v23_deals"
                db.execute(f'DROP TABLE IF EXISTS "{temp}"')
                ddl = _schema_table_ddl("deals")
                ddl = re.sub(
                    r"CREATE TABLE IF NOT EXISTS\s+deals",
                    f'CREATE TABLE "{temp}"',
                    ddl,
                    count=1,
                    flags=re.I,
                )
                db.execute(ddl)

                old_columns = [row["name"] for row in db.execute('PRAGMA table_info("deals")').fetchall()]
                new_columns = [row["name"] for row in db.execute(f'PRAGMA table_info("{temp}")').fetchall()]
                common = [name for name in old_columns if name in new_columns]
                if not common:
                    raise RuntimeError("Deal status migration found no common columns.")

                quoted = ",".join(f'"{name}"' for name in common)
                select_parts = [
                    "CASE WHEN status='INTERESTED' THEN 'DEAL' ELSE status END AS status"
                    if name == "status"
                    else f'"{name}"'
                    for name in common
                ]
                db.execute(
                    f'INSERT INTO "{temp}" ({quoted}) SELECT {",".join(select_parts)} FROM "deals"'
                )
                db.execute('DROP TABLE "deals"')
                db.execute(f'ALTER TABLE "{temp}" RENAME TO "deals"')
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_deals_status_updated "
                    "ON deals(status,updated_at DESC,id DESC)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_deals_followup "
                    "ON deals(followup_date,status,id)"
                )
                db.execute("UPDATE prospects SET status='DEAL' WHERE status='INTERESTED'")
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.execute("PRAGMA foreign_keys=ON")

            violations = db.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"Deal status migration created foreign-key violations: {violations[:5]}")

        db.execute(
            "UPDATE schema_migrations SET name=? WHERE version=?",
            ("rsf-v1.16.1-deal-prospect-deal-status", 21),
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (23, "rsf-v1.18.5-deal-status"),
        )

    # V24 stores the public Contact form phone number separately from email.
    # Existing Website Inquiry rows are preserved and receive an empty phone value.
    if 24 not in applied:
        inquiry_columns = {row["name"] for row in db.execute("PRAGMA table_info(website_inquiries)").fetchall()}
        if "phone" not in inquiry_columns:
            db.execute("ALTER TABLE website_inquiries ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (24, "rsf-v1.18.26-website-inquiry-phone"),
        )

    # V25 adds the shared Website Inquiry -> Deal workflow without reusing the
    # existing inquiry routing status (UNCLAIMED/CLAIMED/ARCHIVED/SPAM).
    if 25 not in applied:
        inquiry_columns = {row["name"] for row in db.execute("PRAGMA table_info(website_inquiries)").fetchall()}
        if "workflow_status" not in inquiry_columns:
            db.execute(
                "ALTER TABLE website_inquiries ADD COLUMN workflow_status TEXT NOT NULL DEFAULT 'NOT_CONTACTED' "
                "CHECK (workflow_status IN ('NOT_CONTACTED','NO_ANSWER','REJECTED','DEAL','DEMO','PROPOSAL','DECISION','WON','LOST'))"
            )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_website_inquiries_workflow "
            "ON website_inquiries(workflow_status,updated_at DESC,id DESC)"
        )

        deal_columns = {row["name"] for row in db.execute("PRAGMA table_info(deals)").fetchall()}
        if using_postgres():
            db.execute("ALTER TABLE deals ALTER COLUMN prospect_id DROP NOT NULL")
            if "website_inquiry_id" not in deal_columns:
                db.execute("ALTER TABLE deals ADD COLUMN website_inquiry_id BIGINT")
            if "contact_person" not in deal_columns:
                db.execute("ALTER TABLE deals ADD COLUMN contact_person TEXT NOT NULL DEFAULT ''")
            if "location" not in deal_columns:
                db.execute("ALTER TABLE deals ADD COLUMN location TEXT NOT NULL DEFAULT ''")
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_deals_website_inquiry_id "
                "ON deals(website_inquiry_id) WHERE website_inquiry_id IS NOT NULL"
            )
        else:
            db.commit()
            db.execute("PRAGMA foreign_keys=OFF")
            try:
                _sqlite_rebuild_table_from_release_schema(db, "deals")
                db.execute("DROP INDEX IF EXISTS idx_deals_status_updated")
                db.execute("DROP INDEX IF EXISTS idx_deals_followup")
                db.execute("CREATE INDEX IF NOT EXISTS idx_deals_status_updated ON deals(status,updated_at DESC,id DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_deals_followup ON deals(followup_date,status,id)")
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.execute("PRAGMA foreign_keys=ON")
            violations = db.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"Website Inquiry Deal migration created foreign-key violations: {violations[:5]}")

        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (25, "rsf-v1.18.50-website-inquiry-deals"),
        )

    # V26 adds Prospect Notes After Conversation and keeps it as the same shared
    # data as the linked Deal field. Existing Deal notes are copied to the
    # Prospect once so no current conversation notes are lost.
    if 26 not in applied:
        prospect_columns = {row["name"] for row in db.execute("PRAGMA table_info(prospects)").fetchall()}
        if "notes_after_conversation" not in prospect_columns:
            db.execute(
                "ALTER TABLE prospects ADD COLUMN notes_after_conversation TEXT NOT NULL DEFAULT ''"
            )
        db.execute(
            """UPDATE prospects
               SET notes_after_conversation=COALESCE(
                   (SELECT d.notes_after_conversation
                    FROM deals d
                    WHERE d.prospect_id=prospects.id
                    LIMIT 1),
                   ''
               )
               WHERE trim(COALESCE(notes_after_conversation,''))=''
                 AND EXISTS (
                     SELECT 1 FROM deals d
                     WHERE d.prospect_id=prospects.id
                       AND trim(COALESCE(d.notes_after_conversation,''))<>''
                 )"""
        )
        db.execute(
            "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
            (26, "rsf-v1.18.63-prospect-deal-notes-sync"),
        )


def _table_exists_postgres(db, table: str) -> bool:
    row = db.execute(
        "SELECT 1 AS ok FROM information_schema.tables WHERE table_schema='public' AND table_name=? LIMIT 1",
        (table,),
    ).fetchone()
    return bool(row)


def _import_legacy_website_inquiries(db) -> None:
    if not using_postgres() or not _table_exists_postgres(db, "contact_inquiries"):
        return
    marker = db.execute("SELECT value FROM settings WHERE key='legacy_contact_inquiries_imported' LIMIT 1").fetchone()
    if marker:
        return
    rows = db.execute(
        "SELECT id,created_at,updated_at,name,email,company,message,status,source_type,source_slug,source_title,source_action "
        "FROM contact_inquiries ORDER BY id"
    ).fetchall()
    for row in rows:
        email = (row.get("email") or "").strip()
        status = "ARCHIVED" if str(row.get("status") or "").lower() == "archived" else "UNCLAIMED"
        db.execute(
            """INSERT INTO website_inquiries(created_at,updated_at,name,email,email_norm,company,message,status,
               source_type,source_slug,source_title,source_action)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(row.get("created_at") or ""), str(row.get("updated_at") or row.get("created_at") or ""),
             row.get("name") or "", email, email.lower(), row.get("company") or "", row.get("message") or "",
             status, row.get("source_type") or "legacy-website", row.get("source_slug") or "",
             row.get("source_title") or "", row.get("source_action") or ""),
        )
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat()
    db.execute("INSERT INTO settings(key,value,updated_at) VALUES (?,?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at",
               ("legacy_contact_inquiries_imported", str(len(rows)), now))
    db.commit()


def _import_seed_payload(db) -> None:
    if not using_postgres():
        return
    marker = db.execute("SELECT value FROM settings WHERE key='online_migration_v151' LIMIT 1").fetchone()
    if marker:
        return
    raw = os.environ.get("RSF_MIGRATION_PAYLOAD_B64", "").strip()
    if not raw:
        return
    payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    tables = payload.get("tables", {})
    order = [
        "users", "account_password_vault", "commission_stages", "partners", "leads", "lead_notes", "followups", "sales", "commissions", "sale_corrections",
        "resources", "duplicate_claims", "activity_log", "messages", "message_attachments", "voice_calls",
        "voice_call_signals", "settings", "website_inquiries", "client_conversations", "client_messages",
        "client_attachments", "client_notifications", "prospects", "deals", "deal_documents"
    ]
    for table in order:
        rows = tables.get(table) or []
        existing_columns = {col["name"] for col in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            clean_row = dict(row)
            if table == "voice_calls" and "receiver_seeen_at" in clean_row and "receiver_seen_at" not in clean_row:
                clean_row["receiver_seen_at"] = clean_row.pop("receiver_seeen_at")
            if table == "deals" and "stage" in clean_row and "status" not in clean_row:
                clean_row["status"] = clean_row.pop("stage")
            # One-time Render recovery payloads can carry SQLite BLOB values as
            # explicit base64 sentinels. Decode them only during the trusted
            # migration import; ordinary application JSON is never interpreted here.
            for key, value in list(clean_row.items()):
                if isinstance(value, dict) and set(value.keys()) == {"__rsf_bytes_b64__"}:
                    clean_row[key] = base64.b64decode(value["__rsf_bytes_b64__"])
            columns = [c for c in clean_row.keys() if c in existing_columns]
            if not columns:
                continue
            placeholders = ",".join("?" for _ in columns)
            quoted = ",".join('"' + c.replace('"','""') + '"' for c in columns)
            sql = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            db.execute(sql, tuple(clean_row[c] for c in columns))
        if rows and "id" in rows[0] and table in SERIAL_ID_TABLES:
            db.execute(
                "SELECT setval(pg_get_serial_sequence(?, 'id'), COALESCE((SELECT MAX(id) FROM " + table + "), 1), true)",
                (table,),
            )
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat()
    db.execute("INSERT INTO settings(key,value,updated_at) VALUES (?,?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at",
               ("online_migration_v151", "complete", now))
    db.commit()



def _import_attachment_seed(db) -> None:
    if not using_postgres():
        return
    marker = db.execute("SELECT value FROM settings WHERE key='online_attachment_migration_v151' LIMIT 1").fetchone()
    if marker:
        return
    key = os.environ.get("RSF_ATTACHMENT_MIGRATION_KEY", "").strip()
    packaged_seed = Path(current_app.root_path).parent / "deployment" / "migration" / "online_attachment_seed.enc"
    render_secret_seed = Path("/etc/secrets/online_attachment_seed.enc")
    seed_path = render_secret_seed if render_secret_seed.is_file() else packaged_seed
    if not key or not seed_path.is_file():
        return
    try:
        from cryptography.fernet import Fernet
        raw_zip = Fernet(key.encode("ascii")).decrypt(seed_path.read_bytes())
        with zipfile.ZipFile(io.BytesIO(raw_zip), "r") as zf:
            for name in zf.namelist():
                if name.startswith("message_uploads/") and not name.endswith("/"):
                    stored = Path(name).name
                    data = zf.read(name)
                    db.execute("UPDATE message_attachments SET data_blob=? WHERE stored_name=?", (data, stored))
                elif name.startswith("client_attachments/") and not name.endswith("/"):
                    stored = Path(name).name
                    data = zf.read(name)
                    db.execute("UPDATE client_attachments SET data_blob=? WHERE stored_name=?", (data, stored))
                elif name.startswith("profile_pictures/") and not name.endswith("/"):
                    stored = Path(name).name
                    data = zf.read(name)
                    db.execute("UPDATE users SET avatar_data=? WHERE avatar_stored_name=?", (data, stored))
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat()
        db.execute("INSERT INTO settings(key,value,updated_at) VALUES (?,?,?) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=EXCLUDED.updated_at",
                   ("online_attachment_migration_v151", "complete", now))
        db.commit()
    except Exception:
        db.rollback()
        raise

def ensure_database() -> None:
    db = get_db()
    schema = (Path(current_app.root_path) / "schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    db.execute(
        "INSERT OR IGNORE INTO schema_migrations(version,name) VALUES (?,?)",
        (1, "rsf-internal-sales-partner-v1"),
    )
    _apply_migrations(db)

    stages = [
        ("FOUNDING_1", "Founding Partner #1", 4000, 1),
        ("EARLY", "Early Partner", 3000, 2),
        ("ESTABLISHED", "Established Sales Partner", 2000, 3),
        ("STANDARD", "Standard Partner", 1500, 4),
    ]
    db.executemany(
        "INSERT OR IGNORE INTO commission_stages(code,name,rate_bp,sort_order) VALUES (?,?,?,?)",
        stages,
    )
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat()
    defaults = [
        ("company_name", "Realty Systems Foundry", now),
        ("currency_code", "USD", now),
    ]
    db.executemany(
        "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES (?,?,?)",
        defaults,
    )
    db.commit()
    _import_seed_payload(db)
    _import_attachment_seed(db)
    _import_legacy_website_inquiries(db)
