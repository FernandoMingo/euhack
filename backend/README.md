# CivicCircles Backend Data Layer

This backend folder contains the first implementation slice for CivicCircles:
- SQLite schema (with migrations directory)
- Python dataclasses for domain and model artifacts
- DB initialization helpers
- repository/query layer on top of `sqlite3`
- activity templates catalog + seed pipeline

## What is implemented

### 1) Database schema
- Directory: `sql/` (migrations applied in filename order)
- `sql/001_initial_schema.sql`:
  - core entities: residents, professionals, referrals, consent
  - activities, circles, invitations, attendance, feedback
  - operator decisions, safety reports, audit events
  - recommendation and ranking artifacts (matching runs, feature scores, similarity, graph)
  - internal peer ratings, rollups, and moderation flags
- `sql/002_activity_templates.sql`:
  - `activity_templates` catalog with rich attributes (family, cost, social energy, setting, intensity, noise, structure, risk)
  - `activity_template_tags` for taxonomy tags used in vectorization

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

### 4) Repository/query layer
- Package: `app/repositories`
- Includes:
  - `ResidentRepository`
  - `ActivityRepository`
  - `ActivityTemplateRepository`
  - `MatchingRepository`
  - `RatingRepository`
- Purpose:
  - centralize SQL access and row-to-dataclass mapping
  - provide typed methods for common create/read/update operations

### 5) Logging
- File: `app/logging_config.py`
- Use `configure_logging()` to set level and formatting.
- Logged areas:
  - database initialization and connection lifecycle in `app/db.py`
  - SQL query operations in `app/repositories/base.py` (debug level)
  - activity catalog seeding in `app/seed.py`

### 6) Activity templates catalog
- Data file: `data/activity_catalog.json`
- Loader: `app/seed.py` (`load_activity_catalog`, `seed_activity_templates`)
- CLI: `scripts/seed_activity_catalog.py`
- Each template captures:
  - identity (`code`, `title`, `description`)
  - taxonomy (`family`)
  - attributes used for matching: typical duration, group size, cost band, social energy, setting, intensity, noise level, structure, risk level
  - free-form `tags` such as `theme:outdoor`, `attribute:creative`, `access:step_free_possible`, `skill:beginner_friendly`
- Templates power activity vectors (cosine similarity) and activity-to-activity similarity.

## Quick start

From repository root:

```bash
python3 backend/init_db.py
```

Custom paths:

```bash
python3 backend/init_db.py \
  --db-path backend/civiccircles.db \
  --schema-path backend/sql
```

Seed the activity templates catalog (initializes the DB if not skipped):

```bash
python3 backend/scripts/seed_activity_catalog.py
```

To seed without re-initializing schema:

```bash
python3 backend/scripts/seed_activity_catalog.py --skip-init
```

## Notes on ranking and privacy

- The system stores **activity/group matching scores** for explainability and reproducibility.
- Cosine similarity artifacts are stored as sparse feature weights + cached similarity outputs.
- Internal peer ratings are stored for internal matching/safety quality signals.
- Peer ratings are intended to be **non-public**; raw pairwise ratings should not be exposed to residents.

## Minimal usage example

```python
from app import ActivityRepository, ResidentRepository, connect, init_db

init_db()
with connect() as conn:
    residents = ResidentRepository(conn)
    activities = ActivityRepository(conn)
    sofia = residents.create_resident(
        first_name="Sofia",
        email="sofia@example.com",
        preferred_language="English",
        city="Amsterdam",
        social_comfort="small_group_low_pressure",
        preferred_group_size_min=3,
        preferred_group_size_max=6,
        cost_sensitivity="free_or_low_cost",
    )
```

## Running tests

From repository root:

```bash
python3 -m unittest discover -s backend/tests -p "test_*.py"
```

Current test coverage includes:
- schema initialization and key table presence
- repository happy-path flows across resident/activity/matching/rating data
- logging behavior for DB initialization and repository query execution

## Logging usage

```python
from app import configure_logging, init_db

configure_logging("DEBUG")
init_db()
```

`INFO` is recommended by default; use `DEBUG` during local development to inspect query-level repository operations.

## Next recommended steps

1. Build a vectorizer that converts activity templates and resident profiles into the same feature space.
2. Persist vectors via `resident_feature_weights` and `activity_feature_weights`.
3. Add a deterministic matching engine that produces ranked candidates with explanations.
4. Add a richer migrations strategy (up/down scripts) for production evolution.

