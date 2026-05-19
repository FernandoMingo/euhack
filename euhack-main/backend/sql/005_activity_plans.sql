PRAGMA foreign_keys = ON;

-- Feature 9 (LLM-backed activity planning) generates a concrete,
-- operator-reviewable plan for a proposed circle anchored to an activity
-- template. The plan is intentionally a *draft* artifact: it never creates
-- an `activities` row or sends invitations on its own. The operator must
-- approve (and may edit) the plan before downstream actions happen.
--
-- A dedicated table is used because the existing schema does not fit
-- cleanly: `activities` requires concrete venue/time data, `operator_decisions`
-- is FK'd to an `activity_id` (which does not exist yet), and
-- `match_explanations` is FK'd to `match_candidate_id` for matching outputs.
-- Keeping prompt metadata, model identity, and the structured JSON output in
-- one table makes the LLM step fully auditable and reproducible.

CREATE TABLE IF NOT EXISTS activity_plans (
    id TEXT PRIMARY KEY,
    circle_id TEXT NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    template_id TEXT REFERENCES activity_templates(id) ON DELETE SET NULL,
    activity_id TEXT REFERENCES activities(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'generated', 'approved', 'rejected', 'edited', 'failed')),
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    request_payload_json TEXT NOT NULL,
    response_json TEXT,
    summary_text TEXT,
    requires_review_flags_json TEXT NOT NULL DEFAULT '[]',
    operator_constraints_json TEXT NOT NULL DEFAULT '{}',
    requested_by TEXT,
    operator_id TEXT,
    decision_reason TEXT,
    edits_json TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_plans_circle ON activity_plans(circle_id);
CREATE INDEX IF NOT EXISTS idx_activity_plans_status ON activity_plans(status, created_at);
