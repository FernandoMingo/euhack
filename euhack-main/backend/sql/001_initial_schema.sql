PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS trusted_professionals (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    organization TEXT,
    city TEXT,
    email TEXT NOT NULL UNIQUE,
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending', 'approved', 'rejected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS residents (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    preferred_language TEXT NOT NULL,
    city TEXT NOT NULL,
    neighborhood TEXT,
    location_radius_km INTEGER NOT NULL CHECK (location_radius_km >= 0),
    social_comfort TEXT NOT NULL,
    preferred_group_size_min INTEGER NOT NULL CHECK (preferred_group_size_min >= 1),
    preferred_group_size_max INTEGER NOT NULL CHECK (preferred_group_size_max >= preferred_group_size_min),
    cost_sensitivity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'withdrawn')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    withdrawn_at TEXT
);

CREATE TABLE IF NOT EXISTS resident_preferences (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    preference_type TEXT NOT NULL CHECK (preference_type IN ('interest', 'activity', 'accessibility_need')),
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (resident_id, preference_type, value)
);

CREATE TABLE IF NOT EXISTS resident_availability (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    weekday TEXT NOT NULL CHECK (weekday IN ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')),
    start_time_local TEXT NOT NULL,
    end_time_local TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resident_avoidances (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (resident_id, value)
);

CREATE TABLE IF NOT EXISTS referrals (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    professional_id TEXT NOT NULL REFERENCES trusted_professionals(id) ON DELETE RESTRICT,
    referral_reason TEXT,
    status TEXT NOT NULL CHECK (status IN ('submitted', 'accepted', 'closed')),
    created_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    professional_id TEXT NOT NULL REFERENCES trusted_professionals(id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
    granted_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consent_scopes (
    id TEXT PRIMARY KEY,
    consent_id TEXT NOT NULL REFERENCES consent_records(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (
        scope IN (
            'create_social_profile',
            'use_profile_for_activity_matching',
            'send_activity_invitations',
            'share_limited_status_with_professional',
            'internal_peer_ratings'
        )
    ),
    UNIQUE (consent_id, scope)
);

CREATE TABLE IF NOT EXISTS venues (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    lat REAL,
    lng REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hosts (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    contact_email TEXT,
    host_type TEXT NOT NULL CHECK (host_type IN ('volunteer', 'city_staff', 'partner_staff', 'facilitator')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    venue_id TEXT NOT NULL REFERENCES venues(id) ON DELETE RESTRICT,
    host_id TEXT REFERENCES hosts(id) ON DELETE SET NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    cost_cents INTEGER NOT NULL DEFAULT 0 CHECK (cost_cents >= 0),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    approval_status TEXT NOT NULL CHECK (approval_status IN ('draft', 'proposed', 'approved', 'rejected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_accessibility (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    accessibility_tag TEXT NOT NULL,
    UNIQUE (activity_id, accessibility_tag)
);

CREATE TABLE IF NOT EXISTS circles (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'invitations_sent', 'confirmed', 'completed', 'cancelled')),
    fit_score REAL CHECK (fit_score >= 0.0 AND fit_score <= 1.0),
    shared_signals_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS circle_members (
    id TEXT PRIMARY KEY,
    circle_id TEXT NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    UNIQUE (circle_id, resident_id)
);

CREATE TABLE IF NOT EXISTS invitations (
    id TEXT PRIMARY KEY,
    circle_id TEXT NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('sent', 'accepted', 'declined', 'expired')),
    companion_pass_used INTEGER NOT NULL DEFAULT 0 CHECK (companion_pass_used IN (0, 1)),
    sent_at TEXT NOT NULL,
    responded_at TEXT,
    UNIQUE (activity_id, resident_id)
);

CREATE TABLE IF NOT EXISTS attendance_events (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    check_in_at TEXT,
    check_out_at TEXT,
    attendance_status TEXT NOT NULL CHECK (attendance_status IN ('invited', 'attended', 'no_show')),
    UNIQUE (activity_id, resident_id)
);

CREATE TABLE IF NOT EXISTS circle_reveal_events (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    revealed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resident_feedback (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    felt_after TEXT CHECK (felt_after IN ('worse', 'same', 'better')),
    activity_fit INTEGER CHECK (activity_fit IN (0, 1)),
    group_comfort INTEGER CHECK (group_comfort IN (0, 1)),
    would_repeat INTEGER CHECK (would_repeat IN (0, 1)),
    safety_reported INTEGER NOT NULL DEFAULT 0 CHECK (safety_reported IN (0, 1)),
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (activity_id, resident_id)
);

CREATE TABLE IF NOT EXISTS operator_decisions (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    operator_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected', 'edited')),
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matching_runs (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL CHECK (run_type IN ('activity_ranking', 'circle_matching', 're_recommendation')),
    model_version TEXT NOT NULL,
    score_algorithm TEXT NOT NULL,
    source_window_start TEXT,
    source_window_end TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_candidates (
    id TEXT PRIMARY KEY,
    matching_run_id TEXT NOT NULL REFERENCES matching_runs(id) ON DELETE CASCADE,
    resident_id TEXT REFERENCES residents(id) ON DELETE CASCADE,
    circle_id TEXT REFERENCES circles(id) ON DELETE CASCADE,
    activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
    total_score REAL NOT NULL,
    rank_position INTEGER NOT NULL CHECK (rank_position > 0),
    hard_constraints_passed INTEGER NOT NULL CHECK (hard_constraints_passed IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_feature_scores (
    id TEXT PRIMARY KEY,
    match_candidate_id TEXT NOT NULL REFERENCES match_candidates(id) ON DELETE CASCADE,
    feature_key TEXT NOT NULL,
    feature_weight REAL NOT NULL,
    feature_score REAL NOT NULL,
    contribution REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_explanations (
    id TEXT PRIMARY KEY,
    match_candidate_id TEXT NOT NULL REFERENCES match_candidates(id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    explanation_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resident_feature_weights (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    feature_key TEXT NOT NULL,
    feature_weight REAL NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE (resident_id, feature_key, model_version)
);

CREATE TABLE IF NOT EXISTS activity_feature_weights (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    feature_key TEXT NOT NULL,
    feature_weight REAL NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE (activity_id, feature_key, model_version)
);

CREATE TABLE IF NOT EXISTS resident_activity_similarity (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    algorithm TEXT NOT NULL,
    model_version TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE (resident_id, activity_id, algorithm, model_version)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id TEXT PRIMARY KEY,
    src_type TEXT NOT NULL CHECK (src_type IN ('resident', 'activity', 'circle', 'host', 'venue')),
    src_id TEXT NOT NULL,
    dst_type TEXT NOT NULL CHECK (dst_type IN ('resident', 'activity', 'circle', 'host', 'venue')),
    dst_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    edge_weight REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS graph_scores (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('activity', 'circle', 'host', 'venue', 'resident_internal')),
    entity_id TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    model_version TEXT NOT NULL,
    score REAL NOT NULL,
    sample_size INTEGER,
    computed_at TEXT NOT NULL,
    UNIQUE (entity_type, entity_id, algorithm, model_version)
);

CREATE TABLE IF NOT EXISTS peer_ratings (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    rater_resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    ratee_resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    comfort_to_be_with INTEGER CHECK (comfort_to_be_with BETWEEN 1 AND 5),
    respectful_behavior INTEGER CHECK (respectful_behavior BETWEEN 1 AND 5),
    reliability_showed_up INTEGER CHECK (reliability_showed_up BETWEEN 1 AND 5),
    group_contribution INTEGER CHECK (group_contribution BETWEEN 1 AND 5),
    note_text TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (rater_resident_id <> ratee_resident_id),
    UNIQUE (activity_id, rater_resident_id, ratee_resident_id)
);

CREATE TABLE IF NOT EXISTS peer_rating_rollups (
    id TEXT PRIMARY KEY,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    model_version TEXT NOT NULL,
    comfort_to_be_with_score REAL,
    respectful_behavior_score REAL,
    reliability_showed_up_score REAL,
    group_contribution_score REAL,
    rating_count INTEGER NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
    confidence REAL,
    recentness_weighted_score REAL,
    computed_at TEXT NOT NULL,
    UNIQUE (resident_id, model_version)
);

CREATE TABLE IF NOT EXISTS peer_rating_flags (
    id TEXT PRIMARY KEY,
    peer_rating_id TEXT NOT NULL REFERENCES peer_ratings(id) ON DELETE CASCADE,
    flag_type TEXT NOT NULL CHECK (flag_type IN ('outlier', 'retaliation_suspected', 'spam_pattern', 'abusive_text')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS safety_reports (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    reporter_resident_id TEXT REFERENCES residents(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL,
    description TEXT,
    escalation_level TEXT NOT NULL CHECK (escalation_level IN ('none', 'operator_review', 'urgent')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('resident', 'professional', 'operator', 'system')),
    actor_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resident_preferences_resident ON resident_preferences(resident_id);
CREATE INDEX IF NOT EXISTS idx_resident_availability_resident ON resident_availability(resident_id);
CREATE INDEX IF NOT EXISTS idx_referrals_professional ON referrals(professional_id);
CREATE INDEX IF NOT EXISTS idx_consent_records_resident ON consent_records(resident_id);
CREATE INDEX IF NOT EXISTS idx_activities_status ON activities(approval_status, start_at);
CREATE INDEX IF NOT EXISTS idx_circle_members_resident ON circle_members(resident_id);
CREATE INDEX IF NOT EXISTS idx_invitations_resident_status ON invitations(resident_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_activity_status ON attendance_events(activity_id, attendance_status);
CREATE INDEX IF NOT EXISTS idx_matching_runs_created ON matching_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_match_candidates_run_rank ON match_candidates(matching_run_id, rank_position);
CREATE INDEX IF NOT EXISTS idx_feature_weights_resident ON resident_feature_weights(resident_id, model_version);
CREATE INDEX IF NOT EXISTS idx_feature_weights_activity ON activity_feature_weights(activity_id, model_version);
CREATE INDEX IF NOT EXISTS idx_similarity_resident ON resident_activity_similarity(resident_id, model_version);
CREATE INDEX IF NOT EXISTS idx_graph_scores_entity ON graph_scores(entity_type, entity_id, model_version);
CREATE INDEX IF NOT EXISTS idx_peer_ratings_ratee ON peer_ratings(ratee_resident_id, created_at);
CREATE INDEX IF NOT EXISTS idx_peer_rating_flags_rating ON peer_rating_flags(peer_rating_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events(entity_type, entity_id, created_at);
