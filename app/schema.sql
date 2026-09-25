PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','partner')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    force_password_change INTEGER NOT NULL DEFAULT 0 CHECK (force_password_change IN (0,1)),
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_login_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    avatar_stored_name TEXT,
    avatar_mime_type TEXT,
    avatar_updated_at TEXT
);

CREATE TABLE IF NOT EXISTS commission_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    rate_bp INTEGER NOT NULL CHECK (rate_bp >= 0 AND rate_bp <= 4000),
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    full_name_snapshot TEXT NOT NULL DEFAULT '',
    email_snapshot TEXT NOT NULL DEFAULT '',
    deleted_at TEXT,
    commission_stage_id INTEGER NOT NULL REFERENCES commission_stages(id),
    phone TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    joined_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_partner_id INTEGER NOT NULL REFERENCES partners(id),
    company_name TEXT NOT NULL,
    company_norm TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    contact_norm TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    email_norm TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    phone_norm TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    website_domain TEXT NOT NULL DEFAULT '',
    lead_source TEXT NOT NULL DEFAULT '',
    summary_notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','CONTACTED','QUALIFIED','DEMO_BOOKED','PROPOSAL','WON','LOST')),
    lost_reason TEXT NOT NULL DEFAULT '',
    demo_at TEXT,
    registered_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_lead_email_norm ON leads(email_norm) WHERE email_norm <> '';
CREATE INDEX IF NOT EXISTS idx_lead_phone_norm ON leads(phone_norm) WHERE phone_norm <> '';
CREATE INDEX IF NOT EXISTS idx_lead_domain ON leads(website_domain) WHERE website_domain <> '';
CREATE INDEX IF NOT EXISTS idx_lead_company_contact ON leads(company_norm, contact_norm) WHERE company_norm <> '' AND contact_norm <> '';
CREATE INDEX IF NOT EXISTS idx_leads_owner ON leads(owner_partner_id, status);
CREATE INDEX IF NOT EXISTS idx_leads_activity ON leads(last_activity_at DESC);

CREATE TABLE IF NOT EXISTS lead_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    author_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    author_name_snapshot TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON lead_notes(lead_id, created_at DESC);

CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    owner_partner_id INTEGER NOT NULL REFERENCES partners(id),
    title TEXT NOT NULL,
    due_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','COMPLETED')),
    completed_at TEXT,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_followups_owner_due ON followups(owner_partner_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_followups_lead ON followups(lead_id, status, due_at);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL UNIQUE REFERENCES leads(id),
    partner_id INTEGER NOT NULL REFERENCES partners(id),
    client_name TEXT NOT NULL,
    product_service TEXT NOT NULL,
    deal_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (deal_amount_cents >= 0),
    invoiced_cents INTEGER NOT NULL DEFAULT 0 CHECK (invoiced_cents >= 0),
    collected_cents INTEGER NOT NULL DEFAULT 0 CHECK (collected_cents >= 0),
    qualifying_revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (qualifying_revenue_cents >= 0),
    payment_status TEXT NOT NULL DEFAULT 'UNPAID' CHECK (payment_status IN ('UNPAID','PARTIALLY_PAID','PAID','REFUNDED_ADJUSTED')),
    sale_date TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (qualifying_revenue_cents <= collected_cents)
);
CREATE INDEX IF NOT EXISTS idx_sales_partner ON sales(partner_id, sale_date DESC);

CREATE TABLE IF NOT EXISTS commissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id),
    partner_id INTEGER NOT NULL REFERENCES partners(id),
    stage_name_snapshot TEXT NOT NULL,
    rate_bp_snapshot INTEGER NOT NULL CHECK (rate_bp_snapshot >= 0 AND rate_bp_snapshot <= 4000),
    qualifying_revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (qualifying_revenue_cents >= 0),
    adjustment_cents INTEGER NOT NULL DEFAULT 0,
    commission_amount_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','PAID')),
    approval_date TEXT,
    paid_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_commissions_partner ON commissions(partner_id, status);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    published INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0,1)),
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_resources_published ON resources(published, category, title);

CREATE TABLE IF NOT EXISTS duplicate_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempted_by_partner_id INTEGER NOT NULL REFERENCES partners(id),
    matched_lead_id INTEGER NOT NULL REFERENCES leads(id),
    company_name TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    reasons TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','DISMISSED','REASSIGNED')),
    resolution_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_duplicate_claims_status ON duplicate_claims(status, created_at DESC);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_name_snapshot TEXT NOT NULL DEFAULT '',
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    description TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_entity ON activity_log(entity_type, entity_id, created_at DESC);


CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    sender_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    body TEXT NOT NULL,
    founder_read_at TEXT,
    partner_read_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_partner ON messages(partner_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_founder_unread ON messages(founder_read_at, partner_id) WHERE founder_read_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_messages_partner_unread ON messages(partner_read_at, partner_id) WHERE partner_read_at IS NULL;

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

CREATE TABLE IF NOT EXISTS voice_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id INTEGER NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
    started_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'RINGING' CHECK (status IN ('RINGING','ACTIVE','ENDED','DECLINED','MISSED')),
    started_at TEXT NOT NULL,
    answered_at TEXT,
    ended_at TEXT,
    end_reason TEXT,
    ended_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    caller_seen_at TEXT,
    receiver_seen_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_voice_calls_partner_status ON voice_calls(partner_id, status, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_voice_calls_open_partner ON voice_calls(partner_id) WHERE status IN ('RINGING','ACTIVE');

CREATE TABLE IF NOT EXISTS voice_call_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL REFERENCES voice_calls(id) ON DELETE CASCADE,
    sender_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('OFFER','ANSWER','ICE')),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_voice_call_signals_call ON voice_call_signals(call_id, id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Unified public website intake and client email workspace (v1.2)
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
    sent_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    sent_by_name_snapshot TEXT NOT NULL DEFAULT '',
    external_message_id TEXT NOT NULL DEFAULT '',
    in_reply_to TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_client_messages_conversation ON client_messages(conversation_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_client_messages_external_id ON client_messages(external_message_id) WHERE external_message_id <> '';
