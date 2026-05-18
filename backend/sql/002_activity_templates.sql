PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS activity_templates (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    family TEXT NOT NULL,
    typical_duration_minutes INTEGER NOT NULL CHECK (typical_duration_minutes > 0),
    typical_group_size_min INTEGER NOT NULL CHECK (typical_group_size_min >= 1),
    typical_group_size_max INTEGER NOT NULL CHECK (typical_group_size_max >= typical_group_size_min),
    typical_cost_band TEXT NOT NULL CHECK (typical_cost_band IN ('free', 'low', 'medium', 'high')),
    social_energy TEXT NOT NULL CHECK (social_energy IN ('low', 'medium', 'high')),
    setting TEXT NOT NULL CHECK (setting IN ('indoor', 'outdoor', 'mixed')),
    intensity TEXT NOT NULL CHECK (intensity IN ('still', 'light', 'active', 'vigorous')),
    noise_level TEXT NOT NULL CHECK (noise_level IN ('quiet', 'moderate', 'loud')),
    structure TEXT NOT NULL CHECK (structure IN ('guided', 'self_paced', 'mixed')),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_template_tags (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES activity_templates(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    UNIQUE (template_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_activity_templates_family ON activity_templates(family);
CREATE INDEX IF NOT EXISTS idx_activity_template_tags_tag ON activity_template_tags(tag);
CREATE INDEX IF NOT EXISTS idx_activity_template_tags_template ON activity_template_tags(template_id);
