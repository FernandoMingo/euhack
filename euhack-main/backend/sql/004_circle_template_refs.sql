PRAGMA foreign_keys = ON;

-- Feature 6 (people/group matching v1) forms small circles around an
-- activity template *or* an approved concrete activity. The original
-- schema declared circles.activity_id as NOT NULL with a foreign key to
-- activities, which means the system could only persist a circle once
-- there was a concrete activity row. Operator-approved circles will
-- still be tied to an activity, but the system needs to propose
-- template-anchored circles ahead of operator approval, so we relax the
-- table to allow either anchor while still requiring at least one. All
-- other constraints stay intact and FOREIGN KEYS remain enabled
-- connection-wide.

DROP INDEX IF EXISTS idx_circle_members_resident;

DROP TABLE IF EXISTS circle_members;
DROP TABLE IF EXISTS circles;

CREATE TABLE circles (
    id TEXT PRIMARY KEY,
    activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
    template_id TEXT REFERENCES activity_templates(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'invitations_sent', 'confirmed', 'completed', 'cancelled')),
    fit_score REAL CHECK (fit_score >= 0.0 AND fit_score <= 1.0),
    shared_signals_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (activity_id IS NOT NULL OR template_id IS NOT NULL)
);

CREATE TABLE circle_members (
    id TEXT PRIMARY KEY,
    circle_id TEXT NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    resident_id TEXT NOT NULL REFERENCES residents(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    UNIQUE (circle_id, resident_id)
);

CREATE INDEX idx_circle_members_resident ON circle_members(resident_id);
CREATE INDEX idx_circles_template ON circles(template_id);
CREATE INDEX idx_circles_activity ON circles(activity_id);
