# CivicCircles Backend Data Layer

This backend folder contains the first implementation slice for CivicCircles:
- SQLite schema (with migrations directory)
- Python dataclasses for domain and model artifacts
- DB initialization helpers
- repository/query layer on top of `sqlite3`
- activity templates catalog + seed pipeline
- deterministic vectorizer and matching engine (Feature 5)
- behavior-aware matching and workflow service (Feature 8 slice)

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
- `sql/003_matching_template_refs.sql`:
  - relaxes the `activity_id` foreign key on `match_candidates`, `activity_feature_weights`, and `resident_activity_similarity` so the matching engine can persist explainability rows that reference activity templates as well as concrete activities
- `sql/004_circle_template_refs.sql`:
  - relaxes `circles.activity_id` to be nullable and adds a nullable `template_id` column so the circle-matching engine can persist proposed circles anchored either to a concrete approved activity or to an activity template before approval. A CHECK constraint enforces that at least one anchor is set.

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
python3 -m pip install -r backend/requirements.txt
```

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

## Matching engine

The package `app/matching` implements Feature 5: a deterministic vectorizer and
ranking engine that scores `activity_templates` for a given resident.

Pipeline (one `MatchingEngine.run_matching` call):

1. **Vectorize the resident** (`vectorizer.build_resident_vector`)
   from `residents`, `resident_preferences`, `resident_availability`, and
   `resident_avoidances` into a sparse `{feature_key: weight}` dict.
   Persisted to `resident_feature_weights` with `model_version='v1'`.
2. **Vectorize every activity template** (`vectorizer.build_template_vector`)
   from `activity_templates` + `activity_template_tags` plus structured
   attributes. Persisted to `activity_feature_weights`.
3. **Hard constraints** (`constraints.check_template_constraints`) reject
   templates that match an avoidance, exceed the resident's cost band, fall
   outside the preferred group size range, would overwhelm a low-pressure
   resident, or are too physically intense given accessibility needs. Each
   rejection records a stable reason string.
4. **Score** (`scoring`) computes cosine similarity over positive feature
   weights (so the value is always in `[0, 1]`) plus soft signals (cost
   alignment, availability presence). Final score is a weighted combination
   (cosine 0.70, availability 0.15, cost 0.15).
5. **Persist + explain** (`engine` + `explain.build_explanation`)
   writes a `matching_runs` row (`run_type='activity_ranking'`,
   `score_algorithm='cosine_weighted'`), a `match_candidates` row per
   template (passing or rejected) with `hard_constraints_passed`, per-feature
   contributions in `match_feature_scores` for passing candidates, a
   `match_explanations` row with summary text + structured JSON for every
   candidate, and updates the `resident_activity_similarity` cosine cache.

Feature key namespace follows AGENTS.md section 10:
`interest:<value>`, `activity_pref:<value>`, `avoid:<value>` (weight
`-1.5`), `access:<value>`, `avail:<weekday>_<bucket>`,
`social_energy:<low|medium|high>`, `group_size:<n>`, `cost:<band>`,
`setting:<value>`, `intensity:<value>`, `noise:<value>`,
`theme:<value>`, `attribute:<value>`, plus `family:<value>`,
`structure:<value>`, `risk:<value>`, `skill:<value>`, `format:<value>`.

Cosine similarity is computed over positive components only, so the score
stays bounded in `[0, 1]` even when the resident vector contains negative
avoidance weights. The avoidance signal still drives constraint rejection.

### Running a matching run

```python
from app import (
    ActivityTemplateRepository, MatchingEngine, MatchingRepository,
    ResidentRepository, configure_logging, connect, init_db,
)
from app.seed import seed_activity_templates

configure_logging("INFO")
init_db()
with connect() as conn:
    seed_activity_templates(conn=conn)
    residents = ResidentRepository(conn)
    templates = ActivityTemplateRepository(conn)
    matching = MatchingRepository(conn)

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
    for value in ("photography", "nature", "outdoor"):
        residents.add_preference(
            resident_id=sofia.id, preference_type="interest", value=value
        )
    residents.add_preference(
        resident_id=sofia.id,
        preference_type="activity",
        value="photography_walk",
    )
    residents.add_availability(
        resident_id=sofia.id, weekday="sat",
        start_time_local="09:00", end_time_local="12:00",
    )

    engine = MatchingEngine(
        residents=residents, templates=templates, matching=matching,
    )
    run_id, top = engine.run_matching(resident_id=sofia.id, top_n=3)
    for result in top:
        print(f"#{result.candidate.rank_position} {result.template.title}: "
              f"total={result.breakdown.total:.3f} "
              f"cosine={result.breakdown.cosine:.3f}")
        print(f"   {result.explanation.summary_text}")
```

Example output (deterministic):

```
#1 Photography Walk: total=0.674 cosine=0.535
   #1 Photography Walk: cosine 0.53, total 0.67. Strong overlap on photography walk, free, 3.
#2 Beginner Birdwatching Walk: total=0.654 cosine=0.506
   #2 Beginner Birdwatching Walk: cosine 0.51, total 0.65. Strong overlap on free, 3, 4.
#3 Coastal Walk: total=0.646 cosine=0.494
   #3 Coastal Walk: cosine 0.49, total 0.65. Strong overlap on free, 3, 4.
```

Two runs over the same input produce the same ordering (tie-break is by
template `code`), so the engine is fully reproducible for audit purposes.

## Circle matching engine (people / group matching v1)

The package `app/matching/grouping.py` implements Feature 6: a
deterministic engine that forms small compatible resident groups
("circles") around a single activity template or an operator-approved
activity. It reuses the Feature 5 vectorizer, hard-constraint checker
and scoring helpers, so a resident filtered out of activity ranking is
also filtered out of circle membership with the same reason strings.

Pipeline (one `CircleEngine.run_grouping` call):

1. **Resolve target.** A `template_code`, `template_id`, or
   `activity_id` is required. When an `activity_id` is provided the
   engine reads the concrete activity and infers the underlying
   template from `activity.activity_type`.
2. **Vectorize the template** (`build_template_vector`) and load the
   candidate residents (defaults to `status='active'`).
3. **Per-resident profiles.** For every candidate the engine builds
   the resident vector, computes the same template-fit score the
   activity-ranking engine produces (cosine + soft signals), captures
   the resident's availability buckets, top interest/theme features
   and social-energy bucket, and runs
   `check_template_constraints`. Residents that fail any hard
   constraint (avoidances, cost band, group-size range, social-energy
   clash, accessibility/intensity, non-active status) are routed to
   the rejected pile with their reason strings preserved.
4. **Deterministic greedy grouping.** Eligible residents are sorted by
   `(-template_score.total, resident.id)`. The engine repeatedly
   picks the next available resident as a seed, then grows the group
   in score order by accepting candidates that:
   - share at least one availability bucket with every current
     member,
   - keep the size within the intersection of every member's
     `[preferred_group_size_min, preferred_group_size_max]` range,
   - and respect a configurable `min_group_size` /
     `max_group_size` window.
   Each resident is used in at most one proposed circle per run.
5. **Group-fit scoring** (pure helpers, no DB access):

   | Component | Weight | Description |
   |---|---|---|
   | `template_fit` | 0.50 | mean per-resident `total_score` from Feature 5 |
   | `availability_density` | 0.20 | count of shared availability buckets, saturating at 3 |
   | `interest_overlap` | 0.15 | size of intersection of positive `interest:` / `theme:` / `attribute:` feature keys, saturating at 3 |
   | `group_size_comfort` | 0.10 | mean comfort over members; 1.0 inside each member's preferred range, decays linearly outside (zero at distance ≥ 2) |
   | `social_energy_consistency` | 0.05 | 1 − (distinct social-energy levels − 1) × 0.4 (so a single shared level → 1.0, three different levels → 0.2) |

   Weights sum to 1.0, output clamped to `[0, 1]`. Ranking is sorted by
   `(-fit_score, tuple(sorted_member_ids))` so two runs over the same
   input emit the same groups in the same order.
6. **Persistence + explainability.** A single `matching_runs` row
   (`run_type='circle_matching'`,
   `score_algorithm='circle_greedy_v1'`) anchors the run. For every
   accepted group the engine creates:
   - a `circles` row (`status='proposed'`, `fit_score`,
     `shared_signals_json` with `shared_availability` and
     `shared_interests`),
   - a `circle_members` row per member,
   - a `match_candidates` row with `circle_id`,
     `hard_constraints_passed=1`, the fit score and rank,
   - one `match_feature_scores` row per group-level component
     (`group:template_fit`, `group:availability_density`,
     `group:interest_overlap`, `group:group_size_comfort`,
     `group:social_energy_consistency`, plus a `group:template_fit_spread`
     diagnostic),
   - and a `match_explanations` row with a short summary and a
     deterministic structured payload describing every member, the
     shared signals, the score components and the model version.

   For every rejected resident the engine writes a
   `match_candidates` row (`resident_id`, `hard_constraints_passed=0`)
   plus a `match_explanations` row capturing the constraint reasons
   so operators can audit who was filtered and why. Invitations are
   not sent and peer-rating tables are not read.

## Behavior-aware matching and workflow service (v2)

Feature 8 adds an opt-in v2 path while keeping the v1 engines stable for
existing callers:

- `app.matching.behavioral` converts safe product interaction data into
  bounded, decayed signals. It only reads invitations, attendance,
  resident feedback, and safety flags; it does not read clinical data or raw
  peer ratings.
- `MatchingEngine(..., model_version="v2", activities=ActivityRepository(...))`
  adds behavior and comfort components to the persisted score breakdown.
  Positive behavior can boost matching on prior templates/families, while
  negative behavior dampens repeats. The behavior boost is capped so explicit
  preferences and hard constraints remain primary.
- `CircleEngine(..., fair_grouping=True, score_algorithm="circle_fair_v2")`
  seeds groups with a bounded fairness priority for residents with fewer
  recent successful matches, penalizes groups with large individual-fit spread,
  and persists eligible-but-unmatched residents with an explanation.
- `MatchingWorkflowService` composes referral acceptance, v2 activity ranking,
  fair circle proposals, operator decision audit rows, and invitation
  promotion for approved activity-backed circles.

The operator-approval rule remains unchanged: proposed circles do not send
invitations until they are anchored to an approved concrete activity.

### Running a circle-matching run

```python
from app import (
    ActivityRepository, ActivityTemplateRepository, CircleEngine,
    MatchingRepository, ResidentRepository, connect, init_db,
)
from app.seed import seed_activity_templates

init_db()
with connect() as conn:
    seed_activity_templates(conn=conn)
    residents = ResidentRepository(conn)
    templates = ActivityTemplateRepository(conn)
    matching = MatchingRepository(conn)
    activities = ActivityRepository(conn)
    # ... create active residents with preferences / availability ...
    engine = CircleEngine(
        residents=residents, templates=templates,
        matching=matching, activities=activities,
    )
    result = engine.run_grouping(
        template_code="photography_walk",
        top_n=3, min_group_size=3, max_group_size=5,
    )
    for group in result.groups:
        print(group.summary_text)
```

A typical summary line looks like:

```
#1 Circle for Photography Walk — 4 residents (Sofia, Marco, Aisha, Bo).
   Fit 0.74 on sat morning, photography.
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
- vectorizer stability, cosine symmetry/bounds, hard-constraint rejection
- end-to-end matching runs (persona ranking, persisted artifacts, determinism)
- circle (group) matching: compatible residents grouped together,
  avoidance / availability / cost rejections, deterministic ordering
  across runs, and persisted rows for `matching_runs`, `circles`,
  `circle_members`, `match_candidates`, `match_feature_scores`, and
  `match_explanations`
- v2 matching: behavior/comfort score components, fair-grouping unmatched
  explanations, and approved-circle invitation promotion with audit rows

## Logging usage

```python
from app import configure_logging, init_db

configure_logging("DEBUG")
init_db()
```

`INFO` is recommended by default; use `DEBUG` during local development to inspect query-level repository operations.

## Next recommended steps

1. Expose thin HTTP/API routes for the v2 matching workflow service.
2. Add richer operator review screens for proposed circles, unmatched residents, and audit explanations.
3. Add a richer migrations strategy (up/down scripts) for production evolution.

