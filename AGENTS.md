# AGENTS.md — CivicCircles Project Context

This file is the source of truth for any AI agent (or new contributor) joining this project. Read this first.

---

## 1. Product summary

CivicCircles is an AI-powered social prescribing platform that helps cities reduce loneliness through small, low-pressure, offline activities. The full product spec lives in [civiccircles_project_spec.md](civiccircles_project_spec.md).

Core ideas:
- Residents are referred by trusted professionals (GPs, social workers, etc.) with explicit consent.
- The AI forms small compatible groups and proposes real-world activities.
- A city operator approves activities before invitations go out.
- The user experience is intentionally minimal; the complex matching, safety, and audit logic lives in operator dashboards.

---

## 2. Engineering principles

- Build **feature by feature**, one commit per feature.
- Each commit message uses prefixes: `feat:`, `chore:`, `fix:`, `docs:`, `refactor:`.
- Each feature should leave the repo working: tests pass, DB seeds, docs updated.
- Prefer **explainable, deterministic logic** over opaque ML for the matching layer.
- Persist enough state to **explain every recommendation** later.

---

## 3. Privacy and safety guardrails

These are hard rules:

- No clinical data (diagnoses, therapy notes, medications) anywhere.
- No public ranking of people.
- No "likeability" or "social score" exposed to users.
- Internal peer ratings exist but are stored for matching/safety quality only:
  - never displayed to other residents
  - only aggregate or thresholded signals influence matching
  - access to raw ratings is restricted to internal roles
- AI **proposes**; humans (operators) **approve**.
- Every AI recommendation must produce a human-readable rationale and a structured rationale.

---

## 4. Tech stack

- Python 3.10+
- SQLite (via `sqlite3` stdlib)
- Plain dataclasses (no ORM yet)
- `unittest` for tests
- Standard `logging` for observability
- No FastAPI/Flask yet — pure data layer + future service layer

---

## 5. Current build state

Feature-by-feature, with file references and commits.

### Built
| Feature | Files | Commit |
|---|---|---|
| SQLite schema + dataclasses | `backend/sql/001_initial_schema.sql`, `backend/app/dataclasses.py`, `backend/app/db.py`, `backend/init_db.py` | `4c73e6a` |
| Repository/query layer | `backend/app/repositories/*.py` | `4a43b16` |
| `.gitignore` for cache/db | `.gitignore` | `6168f9f` |
| Testing + structured logging | `backend/app/logging_config.py`, `backend/tests/*` | `2f78bfa` |
| Activity templates catalog (131 activities) | `backend/sql/002_activity_templates.sql`, `backend/data/activity_catalog.json`, `backend/app/seed.py`, `backend/app/repositories/activity_template_repository.py`, `backend/scripts/seed_activity_catalog.py`, `backend/tests/test_activity_templates.py` | `7bf6a6a` |
| Vectorizer + deterministic matching engine v1 | `backend/sql/003_matching_template_refs.sql`, `backend/app/matching/*.py`, `backend/app/repositories/resident_repository.py`, `backend/tests/test_matching_engine.py` | `e3525b8` |

### Not built yet
- Behavioral signals (recent attendance / feedback decay) in the resident vectorizer
- Service layer composing repositories + matching engine for end-to-end flows (referral → matching → operator review)
- HTTP/API layer
- Frontend

---

## 6. Directory map

```
euhack/
├── AGENTS.md                          (this file)
├── README.md
├── civiccircles_project_spec.md       (full product spec)
├── backend/
│   ├── README.md                      (developer docs for backend)
│   ├── init_db.py                     (CLI: applies all sql/*.sql migrations)
│   ├── app/
│   │   ├── __init__.py                (public exports)
│   │   ├── db.py                      (connect + init_db with migration scan)
│   │   ├── dataclasses.py             (all domain + model dataclasses)
│   │   ├── logging_config.py
│   │   ├── seed.py                    (catalog loader + seeder)
│   │   ├── matching/
│   │   │   ├── __init__.py            (public matching API)
│   │   │   ├── vectorizer.py          (resident + template feature vectors)
│   │   │   ├── constraints.py         (hard-constraint checks)
│   │   │   ├── scoring.py             (pure cosine + weighted score)
│   │   │   ├── explain.py             (summary + structured rationale)
│   │   │   └── engine.py              (orchestrator: persist + rank)
│   │   └── repositories/
│   │       ├── base.py
│   │       ├── resident_repository.py
│   │       ├── activity_repository.py
│   │       ├── activity_template_repository.py
│   │       ├── matching_repository.py
│   │       └── rating_repository.py
│   ├── data/
│   │   └── activity_catalog.json      (131 activity templates)
│   ├── scripts/
│   │   └── seed_activity_catalog.py   (CLI seeder)
│   ├── sql/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_activity_templates.sql
│   │   └── 003_matching_template_refs.sql
│   └── tests/
│       ├── test_db_schema.py
│       ├── test_repositories.py
│       ├── test_logging.py
│       ├── test_activity_templates.py
│       └── test_matching_engine.py
```

---

## 7. Database overview

Key entities and what they exist for:

- **People**: `residents`, `trusted_professionals`, `hosts`
- **Profile signals**: `resident_preferences`, `resident_availability`, `resident_avoidances`
- **Consent and referrals**: `consent_records`, `consent_scopes`, `referrals`
- **Activities (real instances)**: `activities`, `venues`, `activity_accessibility`
- **Activity catalog (templates)**: `activity_templates`, `activity_template_tags`
- **Group formation**: `circles`, `circle_members`
- **Lifecycle**: `invitations`, `attendance_events`, `circle_reveal_events`, `resident_feedback`
- **Operator decisions**: `operator_decisions`
- **Matching artifacts**: `matching_runs`, `match_candidates`, `match_feature_scores`, `match_explanations`
- **Vectorization and similarity**: `resident_feature_weights`, `activity_feature_weights`, `resident_activity_similarity`
- **Graph signals (activity/group only)**: `graph_edges`, `graph_scores`
- **Internal peer ratings**: `peer_ratings`, `peer_rating_rollups`, `peer_rating_flags`
- **Safety and audit**: `safety_reports`, `audit_events`

The schema enforces foreign keys, has check constraints on enum values, and uses upsert patterns where appropriate.

---

## 8. How to run things

From repo root.

Initialize / re-init the database:
```bash
python3 backend/init_db.py
```

Seed the activity templates catalog:
```bash
python3 backend/scripts/seed_activity_catalog.py
```

Run all tests:
```bash
PYTHONPATH="$(pwd)/backend" python3 -m unittest discover -s backend/tests -p "test_*.py"
```

Enable verbose logging in code:
```python
from app import configure_logging
configure_logging("DEBUG")
```

---

## 9. Activity catalog taxonomy

131 activity templates organized by `family`:

- `walks_outdoor`, `food_drink`, `pubs_social`
- `sports_casual`, `sports_active`
- `arts_crafts`, `cultural`, `photography`
- `reading_writing`, `debate_intellectual`
- `videogames`, `tabletop_games`, `music`
- `wellness_mind_body`, `learning_workshops`
- `gardening_nature`, `volunteering_civic`
- `repair_diy`, `special_events`

Each template carries structured attributes used for vectorization:
- `family` (taxonomy bucket)
- `typical_duration_minutes`, `typical_group_size_min/max`
- `typical_cost_band` (`free` | `low` | `medium` | `high`)
- `social_energy` (`low` | `medium` | `high`)
- `setting` (`indoor` | `outdoor` | `mixed`)
- `intensity` (`still` | `light` | `active` | `vigorous`)
- `noise_level` (`quiet` | `moderate` | `loud`)
- `structure` (`guided` | `self_paced` | `mixed`)
- `risk_level` (`low` | `medium` | `high`)
- free-form `tags` like `theme:outdoor`, `attribute:creative`, `access:step_free_possible`, `skill:beginner_friendly`

---

## 10. Next feature to build

**Feature 6: Behavioral signals in the resident vectorizer + service layer.**

The deterministic matching engine v1 is now built (see section 5). The next
work is to feed behavioral signals into the resident vector and to wrap the
engine in a service layer for end-to-end flows.

Scope:
1. Fold recent attendance and feedback signals into resident feature weights
   with exponential decay (e.g. `0.95^weeks`).
2. Add a service layer that composes repositories + `MatchingEngine` for
   referral acceptance → matching → operator review.
3. Wire `audit_events` rows around every state transition (referral
   acceptance, matching run, operator decision).

Feature key naming conventions in use (residents + activity templates):
- `interest:<value>`
- `activity_pref:<value>`
- `avoid:<value>` (negative weight, currently `-1.5`)
- `access:<value>`
- `avail:<weekday>_<bucket>` (e.g. `avail:sat_morning`)
- `social_energy:<low|medium|high>`
- `group_size:<n>` (one feature per n in the preferred / typical range)
- `cost:<band>`
- `family:<value>`, `setting:<value>`, `intensity:<value>`,
  `noise:<value>`, `structure:<value>`, `risk:<value>`
- `theme:<value>`, `attribute:<value>`, `skill:<value>`, `format:<value>`
  (mirrored from `activity_template_tags`)

Current weight model (v1):
- explicit profile features: 1.0
- mirrored interest signals derived from `theme:` tags: 1.0
- mirrored interest signals derived from `attribute:` tags: 0.7
- title/code token derived interest signals: 0.6
- strong avoidances: −1.5
- structure / risk / skill / format features: 0.5

Planned for v2:
- recent positive behavior: 1.1–1.3
- exponential decay on old behavior (e.g. `0.95^weeks`)

---

## 11. Commit history conventions

Current branch `fer/features` history:
```
592205f chore: expand matching engine test + logging coverage
cb7c2e2 docs: record feature 5 commit hash in AGENTS.md
e3525b8 feat: add vectorizer and deterministic matching engine v1
7bf6a6a feat: add activity templates catalog with 131 seedable activities
2f78bfa feat: add backend testing and structured logging support
6168f9f chore: ignore local Python cache and SQLite artifacts
4a43b16 feat: add repository query layer for SQLite data access
4c73e6a feat: add SQLite schema and typed backend data models
4021dc8 Initial commit
```

Rules:
- one feature per commit
- subject line under ~70 chars
- body explains the "why"
- never rewrite history once pushed
- artifacts (DB files, `__pycache__`) are ignored

---

## 12. Things to NOT do

- Do not introduce ORMs or migration frameworks without an explicit decision.
- Do not store clinical data, even for testing.
- Do not expose peer ratings to users or in any public API.
- Do not commit `backend/civiccircles.db` or `__pycache__`.
- Do not combine multiple features in a single commit.
- Do not add silent fallbacks that mask matching errors; matching must be auditable.

---

## 13. Quick onboarding checklist for a new agent

1. Read this file.
2. Skim `backend/README.md`.
3. Run the test suite — it should be all green.
4. Run `python3 backend/scripts/seed_activity_catalog.py` to populate the catalog.
5. Inspect `backend/data/activity_catalog.json` to understand the activity space.
6. Implement the next feature listed in section 10.
