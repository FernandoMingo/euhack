# CivicCircles Backend Data Layer

This backend folder contains the first implementation slice for CivicCircles:
- SQLite schema
- Python dataclasses for domain and model artifacts
- DB initialization helpers

## What is implemented

### 1) Database schema
- File: `sql/001_initial_schema.sql`
- Includes core entities:
  - residents, professionals, referrals, consent
  - activities, circles, invitations, attendance, feedback
  - operator decisions, safety reports, audit events
- Includes recommendation and ranking artifacts:
  - matching runs and candidate scoring
  - per-feature score contributions and explanations
  - resident/activity feature vectors for cosine similarity
  - graph edges/scores for graph-based ranking
  - internal peer ratings, rollups, and moderation flags

### 2) Python dataclasses
- File: `app/dataclasses.py`
- Provides typed dataclasses for:
  - core product entities (`Resident`, `Activity`, `Circle`, `Invitation`, etc.)
  - matching entities (`MatchingRun`, `MatchCandidate`, `MatchFeatureScore`)
  - model outputs (`ResidentActivitySimilarity`, `GraphScore`)
  - internal rating entities (`PeerRating`, `PeerRatingRollup`, `PeerRatingFlag`)

### 3) DB connection and initialization
- File: `app/db.py`
  - `connect()` opens SQLite with FK enforcement and pragmatic defaults.
  - `init_db()` executes the schema script.
- File: `init_db.py`
  - CLI entrypoint to create/init the database.

## Quick start

From repository root:

```bash
python3 backend/init_db.py
```

Custom paths:

```bash
python3 backend/init_db.py \
  --db-path backend/civiccircles.db \
  --schema-path backend/sql/001_initial_schema.sql
```

## Notes on ranking and privacy

- The system stores **activity/group matching scores** for explainability and reproducibility.
- Cosine similarity artifacts are stored as sparse feature weights + cached similarity outputs.
- Internal peer ratings are stored for internal matching/safety quality signals.
- Peer ratings are intended to be **non-public**; raw pairwise ratings should not be exposed to residents.

## Next recommended steps

1. Add repository/query layer on top of `sqlite3`.
2. Add migrations strategy (up/down scripts) after `001_initial_schema.sql`.
3. Add seed data script for demo persona(s).
4. Add tests for constraints and matching persistence integrity.

