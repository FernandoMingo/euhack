PRAGMA foreign_keys = ON;

-- Feature 10 (resident invitation inbox) adds two tables that hang off the
-- existing `invitations` lifecycle but model concerns the lifecycle table
-- intentionally does not carry:
--
--   * `resident_inbox_items` is the resident-facing message view. One inbox
--     item is created per invitation when an operator promotes an approved
--     circle. The body is privacy-safe English copy: activity title, when,
--     where, and a short low-pressure invitation note. It deliberately does
--     not store matching scores, peer ratings, or other residents' names.
--
--   * `outbound_email_messages` is the email-delivery queue/audit. Each row
--     captures the (placeholder) email payload, target address, provider,
--     delivery status, and any provider message id / error. Real sends go
--     through an `EmailClient` injected at app construction time; the
--     default implementation only queues, so no real email is dispatched
--     unless an operator (or a configured provider) decides to send.
--
-- Splitting these from `invitations` keeps the lifecycle table small and
-- audit-friendly while letting the inbox / delivery surfaces evolve.

CREATE TABLE IF NOT EXISTS resident_inbox_items (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    invitation_id TEXT REFERENCES invitations(id) ON DELETE SET NULL,
    activity_id TEXT REFERENCES activities(id) ON DELETE SET NULL,
    circle_id TEXT REFERENCES circles(id) ON DELETE SET NULL,
    item_type TEXT NOT NULL CHECK (item_type IN ('activity_invitation')),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unread' CHECK (status IN ('unread', 'read', 'archived')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    read_at TEXT,
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_resident_inbox_items_resident
    ON resident_inbox_items(resident_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_resident_inbox_items_invitation
    ON resident_inbox_items(invitation_id);

CREATE TABLE IF NOT EXISTS outbound_email_messages (
    id TEXT PRIMARY KEY,
    inbox_item_id TEXT REFERENCES resident_inbox_items(id) ON DELETE SET NULL,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    provider TEXT NOT NULL,
    delivery_status TEXT NOT NULL CHECK (delivery_status IN ('queued', 'sent', 'failed', 'skipped')),
    provider_message_id TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbound_email_messages_status
    ON outbound_email_messages(delivery_status, created_at);
CREATE INDEX IF NOT EXISTS idx_outbound_email_messages_resident
    ON outbound_email_messages(resident_id, created_at);
