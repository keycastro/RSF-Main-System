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

SCHEMA_VERSION = 11
SCHEMA_NAME = "rsf-unified-system-v1.5.1-online-postgres"
SERIAL_ID_TABLES = {"users","commission_stages","partners","leads","lead_notes","followups","sales","commissions","resources","duplicate_claims","activity_log","messages","message_attachments","voice_calls","voice_call_signals","website_inquiries","client_conversations","client_messages","client_attachments","client_notifications"}


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
        if table_name in SERIAL_ID_TABLES and not original_ignore:
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
        "users", "commission_stages", "partners", "leads", "lead_notes", "followups", "sales", "commissions",
        "resources", "duplicate_claims", "activity_log", "messages", "message_attachments", "voice_calls",
        "voice_call_signals", "settings", "website_inquiries", "client_conversations", "client_messages",
        "client_attachments", "client_notifications"
    ]
    for table in order:
        rows = tables.get(table) or []
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            columns = list(row.keys())
            placeholders = ",".join("?" for _ in columns)
            quoted = ",".join('"' + c.replace('"','""') + '"' for c in columns)
            sql = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            db.execute(sql, tuple(row[c] for c in columns))
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
    seed_path = Path(current_app.root_path).parent / "online_attachment_seed.enc"
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
