PRAGMA foreign_keys = ON;

-- Feature 5 (matching engine v1) needs to persist explainability rows that
-- reference activity_templates as well as concrete activities. The original
-- schema declared activity_id as a FOREIGN KEY against activities(id) on
-- three matching-artifact tables, which forbids template ids. We relax the
-- column to a plain TEXT (still indexed) so the engine can write template
-- ids without creating shadow Activity rows. All other constraints stay
-- intact and FOREIGN KEYS remain enabled connection-wide.

DROP INDEX IF EXISTS idx_match_candidates_run_rank;
DROP INDEX IF EXISTS idx_feature_weights_activity;
DROP INDEX IF EXISTS idx_similarity_resident;

DROP TABLE IF EXISTS match_candidates;
DROP TABLE IF EXISTS activity_feature_weights;
DROP TABLE IF EXISTS resident_activity_similarity;

CREATE TABLE match_candidates (
    id TEXT PRIMARY KEY,
    matching_run_id TEXT NOT NULL REFERENCES matching_runs(id) ON DELETE CASCADE,
    resident_id TEXT REFERENCES residents(id) ON DELETE CASCADE,
    circle_id TEXT REFERENCES circles(id) ON DELETE CASCADE,
    activity_id TEXT,
    total_score REAL NOT NULL,
    rank_position INTEGER NOT NULL CHECK (rank_position > 0),
    hard_constraints_passed INTEGER NOT NULL CHECK (hard_constraints_passed IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE activity_feature_weights (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL,
    feature_key TEXT NOT NULL,
    feature_weight REAL NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE (activity_id, feature_key, model_version)
);

CREATE TABLE resident_activity_similarity (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    activity_id TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    model_version TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE (resident_id, activity_id, algorithm, model_version)
);

CREATE INDEX idx_match_candidates_run_rank ON match_candidates(matching_run_id, rank_position);
CREATE INDEX idx_feature_weights_activity ON activity_feature_weights(activity_id, model_version);
CREATE INDEX idx_similarity_resident ON resident_activity_similarity(resident_id, model_version);
