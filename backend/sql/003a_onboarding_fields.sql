PRAGMA foreign_keys = ON;

ALTER TABLE trusted_professionals ADD COLUMN agb_code TEXT;
ALTER TABLE trusted_professionals ADD COLUMN big_number TEXT;
ALTER TABLE trusted_professionals ADD COLUMN qualification TEXT;
ALTER TABLE trusted_professionals ADD COLUMN onderneming_agb_code TEXT;
ALTER TABLE trusted_professionals ADD COLUMN verified_at TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_professionals_agb_code
    ON trusted_professionals(agb_code)
    WHERE agb_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS professional_verifications (
    id TEXT PRIMARY KEY,
    professional_id TEXT NOT NULL REFERENCES trusted_professionals(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN ('passed', 'failed')),
    agb_response_json TEXT,
    big_response_json TEXT,
    kvk_response_json TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_professional_verifications_professional
    ON professional_verifications(professional_id, created_at);

ALTER TABLE consent_records ADD COLUMN consent_text_version TEXT NOT NULL DEFAULT 'v1.0-nl-2026-05';
ALTER TABLE consent_records ADD COLUMN consent_locale TEXT NOT NULL DEFAULT 'nl';
ALTER TABLE consent_records ADD COLUMN capture_method TEXT NOT NULL DEFAULT 'in_consult'
    CHECK (capture_method IN ('in_consult', 'self_completion'));
