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
- FastAPI + Pydantic for the current HTTP API layer
- Uvicorn for local API serving
- `unittest` for tests, including FastAPI `TestClient` coverage
- Standard `logging` for observability
- SQL migrations are plain `.sql` files applied in filename order; no migration framework yet

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
| Deterministic people/group matching v1 (circle engine) | `backend/sql/004_circle_template_refs.sql`, `backend/app/matching/grouping.py`, `backend/app/repositories/activity_repository.py`, `backend/app/dataclasses.py`, `backend/tests/test_circle_engine.py` | `f314946` |
| GP onboarding service + stub verification | `backend/sql/003_onboarding_fields.sql`, `backend/app/services/*.py`, `backend/app/repositories/professional_repository.py`, `backend/app/repositories/consent_repository.py`, `backend/app/repositories/referral_repository.py`, `backend/tests/test_onboarding_service.py` | `0892299` / `842b397` merge |
| FastAPI HTTP API across core repositories | `backend/app/api/**/*.py`, `backend/requirements.txt`, `backend/tests/test_api_*.py`, `backend/tests/test_onboarding_api.py` | `2b6659a` / `842b397` merge |
| Behavioral matching v2 + fair grouping workflow slice | `backend/app/matching/behavioral.py`, `backend/app/matching/vectorizer.py`, `backend/app/matching/scoring.py`, `backend/app/matching/engine.py`, `backend/app/matching/grouping.py`, `backend/app/services/matching_service.py`, `backend/tests/test_matching_service.py` | pending |
| LLM-backed activity planning (operator-reviewable plans) | `backend/sql/005_activity_plans.sql`, `backend/app/services/activity_planning_service.py`, `backend/app/services/llm_client.py`, `backend/app/repositories/activity_plan_repository.py`, `backend/app/api/routers/operator.py`, `backend/tests/test_activity_planning_service.py`, `backend/tests/test_api_activity_planning.py` | pending |
| Resident invitation inbox + outbound email queue | `backend/sql/006_invitation_inbox.sql`, `backend/app/services/invitation_inbox_service.py`, `backend/app/services/email_client.py`, `backend/app/repositories/resident_inbox_repository.py`, `backend/app/repositories/outbound_email_repository.py`, `backend/app/api/routers/inbox.py`, `backend/app/api/routers/operator.py`, `backend/tests/test_invitation_inbox_service.py`, `backend/tests/test_api_inbox.py` | pending |

### Not built yet
- Production Vektis/CIBG/KvK verification integrations; current verification is a deterministic stub
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
│   │   ├── api/
│   │   │   ├── main.py                (FastAPI app factory)
│   │   │   ├── __main__.py            (CLI: python -m app.api)
│   │   │   ├── schemas.py             (Pydantic request/response models)
│   │   │   ├── converters.py          (dataclass → API response mapping)
│   │   │   ├── deps.py                (per-request DB connection dependency)
│   │   │   └── routers/               (health, professionals, referrals, residents,
│   │   │                                templates, activities, invitations, consents,
│   │   │                                inbox, operator)
│   │   ├── matching/
│   │   │   ├── __init__.py            (public matching API)
│   │   │   ├── vectorizer.py          (resident + template feature vectors)
│   │   │   ├── constraints.py         (hard-constraint checks)
│   │   │   ├── scoring.py             (pure cosine + weighted score)
│   │   │   ├── explain.py             (summary + structured rationale)
│   │   │   ├── engine.py              (activity-ranking orchestrator)
│   │   │   └── grouping.py            (deterministic circle/group matching v1)
│   │   ├── services/
│   │   │   ├── activity_planning_service.py (LLM-backed activity plan drafts)
│   │   │   ├── email_client.py          (EmailClient: queued, Resend, fake)
│   │   │   ├── invitation_inbox_service.py (resident inbox + email queueing)
│   │   │   ├── llm_client.py            (LLMClient interface + OpenAI impl)
│   │   │   ├── matching_service.py       (matching workflow orchestration)
│   │   │   ├── onboarding_service.py  (professional signup + resident referral flow)
│   │   │   └── verification_service.py (stub AGB/BIG/KvK verification)
│   │   └── repositories/
│   │       ├── base.py
│   │       ├── resident_repository.py
│   │       ├── resident_inbox_repository.py
│   │       ├── outbound_email_repository.py
│   │       ├── activity_repository.py
│   │       ├── activity_template_repository.py
│   │       ├── activity_plan_repository.py
│   │       ├── professional_repository.py
│   │       ├── consent_repository.py
│   │       ├── referral_repository.py
│   │       ├── matching_repository.py
│   │       └── rating_repository.py
│   ├── data/
│   │   └── activity_catalog.json      (131 activity templates)
│   ├── scripts/
│   │   └── seed_activity_catalog.py   (CLI seeder)
│   ├── sql/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_activity_templates.sql
│   │   ├── 003_onboarding_fields.sql
│   │   ├── 003_matching_template_refs.sql
│   │   ├── 004_circle_template_refs.sql
│   │   ├── 005_activity_plans.sql
│   │   └── 006_invitation_inbox.sql
│   └── tests/
│       ├── test_db_schema.py
│       ├── test_repositories.py
│       ├── test_logging.py
│       ├── test_activity_templates.py
│       ├── test_matching_engine.py
│       ├── test_circle_engine.py
│       ├── test_onboarding_service.py
│       ├── test_onboarding_api.py
│       ├── test_api_templates.py
│       ├── test_api_residents.py
│       ├── test_api_activities.py
│       ├── test_api_invitations_consents.py
│       ├── test_api_operator.py
│       ├── test_activity_planning_service.py
│       ├── test_api_activity_planning.py
│       ├── test_invitation_inbox_service.py
│       └── test_api_inbox.py
```

---

## 7. Database overview

Key entities and what they exist for:

- **People**: `residents`, `trusted_professionals`, `hosts`
- **Profile signals**: `resident_preferences`, `resident_availability`, `resident_avoidances`
- **Consent and referrals**: `consent_records`, `consent_scopes`, `referrals`
- **Professional verification**: `professional_verifications` plus AGB/BIG/KvK fields on `trusted_professionals`
- **Activities (real instances)**: `activities`, `venues`, `activity_accessibility`
- **Activity catalog (templates)**: `activity_templates`, `activity_template_tags`
- **Group formation**: `circles`, `circle_members`
- **Lifecycle**: `invitations`, `attendance_events`, `circle_reveal_events`, `resident_feedback`
- **Operator decisions**: `operator_decisions`
- **Matching artifacts**: `matching_runs`, `match_candidates`, `match_feature_scores`, `match_explanations`
- **Vectorization and similarity**: `resident_feature_weights`, `activity_feature_weights`, `resident_activity_similarity`
- **Graph signals (activity/group only)**: `graph_edges`, `graph_scores`
- **Internal peer ratings**: `peer_ratings`, `peer_rating_rollups`, `peer_rating_flags`
- **LLM-generated planning artifacts**: `activity_plans` (prompt payload + model metadata + structured plan JSON + operator decision)
- **Resident inbox + email queue**: `resident_inbox_items` (resident-facing invitation messages with `unread`/`read`/`archived` state), `outbound_email_messages` (queued / sent / failed delivery audit per resident)
- **Safety and audit**: `safety_reports`, `audit_events`

The schema enforces foreign keys, has check constraints on enum values, and uses upsert patterns where appropriate.

---

## 8. How to run things

From repo root.

Install backend dependencies:
```bash
python3 -m pip install -r backend/requirements.txt
```

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

Run the FastAPI app locally:
```bash
PYTHONPATH="$(pwd)/backend" python3 -m app.api --host 127.0.0.1 --port 8000
```

Enable verbose logging in code:
```python
from app import configure_logging
configure_logging("DEBUG")
```

Run the FastAPI app with the LLM-backed activity-planning service:
```bash
printf 'OPENAI_API_KEY=sk-...\n' > .env
PYTHONPATH="$(pwd)/backend" python3 -m app.api --host 127.0.0.1 --port 8000
```

Optional: send real invitation email when operators promote approved
circles. Two providers ship; `build_email_client_from_env()` picks SMTP
first, then Resend.

Gmail SMTP via App Password (no custom domain needed — recommended for
local/demo use; requires 2-Step Verification + an App Password from
<https://myaccount.google.com/apppasswords>):

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD='xxxx xxxx xxxx xxxx'
EMAIL_FROM='CivicCircles <you@gmail.com>'
```

Resend (production-style, needs a verified sender domain):

```bash
RESEND_API_KEY=re_...
EMAIL_FROM='CivicCircles <invites@your-verified-domain.example>'
```

The CLI loads `.env` from the repo root (and accepts `.emv` as a
typo-tolerant alias). If `OPENAI_API_KEY` is unset or `openai` is not
installed, the planning endpoints respond with HTTP 503 — every other route
still works.

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

**Feature 10: Resident invitation inbox + email queue (built).**

When an operator promotes an approved circle to invitations, each invited
resident now receives:

1. an `invitations` lifecycle row (as before),
2. a `resident_inbox_items` row with a privacy-safe English invitation
   (activity title, time, venue, short low-pressure body), and
3. an `outbound_email_messages` row delivered through a pluggable
   `EmailClient`. The default path uses `QueuedEmailClient`, which never
   sends a real message; rows stay `queued` until you wire Resend (via
   `RESEND_API_KEY` + `EMAIL_FROM` on the API CLI), inject `ResendEmailClient`
   in `create_app`, or mark rows sent manually. Tests inject a
   `FakeEmailClient` that records sends without dispatching them.

Implemented:

1. `sql/006_invitation_inbox.sql` adds `resident_inbox_items` and
   `outbound_email_messages` tables. Inbox items track item type, title,
   body, `unread`/`read`/`archived` status, read/archived timestamps,
   and a privacy-safe `metadata_json`. Email messages track the target
   address, subject/body, provider, delivery status, and provider/error
   metadata.
2. `ResidentInboxItem` + `OutboundEmailMessage` dataclasses and matching
   `ResidentInboxRepository` / `OutboundEmailRepository`.
3. `app/services/email_client.py` exposes a narrow `EmailClient` protocol,
 `QueuedEmailClient` (default no-send), `SMTPEmailClient` (stdlib
 `smtplib`; works with Gmail SMTP + App Password — no custom domain
 required), `ResendEmailClient` (Resend HTTP API via `httpx`),
 `build_email_client_from_env()` (prefers SMTP env vars, falls back to
 Resend), and `FakeEmailClient` (test double).
4. `app/services/invitation_inbox_service.py` composes inbox-item creation +
   email queueing for every invitation. It is invoked from inside
   `MatchingWorkflowService.send_invitations_for_approved_circle` so the
   lifecycle row, inbox item, and queued email stay consistent inside one
   transaction.
5. Resident-facing endpoints under `/api/residents/{resident_id}/inbox`:
   `GET /` (with `?status=unread|read|archived`), `GET /{item_id}`,
   `POST /{item_id}/read`, `POST /{item_id}/archive`. Routes enforce that
   the item belongs to the resident in the path.
6. Operator endpoints under `/api/operator`:
   `GET /email-messages?status=queued`, `GET /email-messages/{id}`,
   `POST /email-messages/{id}/mark-sent`.
7. Audit events: `inbox_item.created`, `email_message.queued`,
   `email_message.sent`, `email_message.failed`.
8. `create_app(..., email_client=...)` wires the configured email client.
 The default omits the parameter so tests and programmatic callers keep
 the queued path. `python -m app.api` loads `.env` and calls
 `build_email_client_from_env()`, which picks `SMTPEmailClient` when
 `SMTP_HOST` + `SMTP_USERNAME` + `SMTP_PASSWORD` (+ optional `EMAIL_FROM`)
 are set (Gmail SMTP works out of the box with an App Password), or
 `ResendEmailClient` when `RESEND_API_KEY` + `EMAIL_FROM` are set.

Privacy guardrails enforced here:

- Inbox copy contains only activity title / time / venue and a short
  warm message. It never contains fit scores, peer ratings, matching
  rationales, or other residents' names.
- The inbox `metadata_json` is restricted to IDs (`invitation_id`,
  `activity_id`, `circle_id`) plus activity/venue identity. It is not a
  carrier for scoring or peer-rating data.
- Resident inbox endpoints check item ownership before responding.
- The default `EmailClient` never sends real email until you opt in
 (SMTP/Gmail or Resend env vars on the CLI, or inject `SMTPEmailClient` /
 `ResendEmailClient` yourself).

**Feature 9: LLM-backed operator-reviewable activity plans (built).**

This feature attaches between proposed circles and operator-approved
concrete activities. `ActivityPlanningService` takes a proposed circle
(template + shared signals + member count + fixed Rotterdam venue-search
context + fixed `output_language=English` + optional operator constraints),
calls the configured LLM with web search enabled, and persists a structured
English-language plan that the operator must
explicitly approve / edit / reject before any real activity row is created
or invitations are sent.

Implemented:
1. `sql/005_activity_plans.sql` adds a dedicated `activity_plans` table
   (prompt payload, model identity, prompt version, structured response,
   operator decision + edits, failure reason).
2. `ActivityPlan` dataclass + `ActivityPlanRepository`.
3. `app/services/llm_client.py` exposes a narrow `LLMClient` protocol and
   `OpenAIChatLLMClient`. The `openai` SDK is imported lazily,
   `OPENAI_API_KEY` is read from the environment, and OpenAI web search is
   enabled by default via the Responses API; missing key/package raises
   `LLMConfigurationError` so failures are explicit.
4. `ActivityPlanningService` enforces hard guardrails:
   - the prompt payload is assembled from template attributes/tags, shared
     availability/interest signals, member count, fixed Rotterdam city
     context, fixed English output language, optional operator-supplied
     `search_area`, optional concrete activity row, and operator constraints —
     never per-resident identifiers or user locations;
   - a defensive substring check (`diagnos`, `therapy`, `medication`,
     `peer_rating`, ...) blocks serialization if forbidden tokens reach the
     payload;
   - prompts, JSON schema, model identity, English-language response contract,
     and `venue_research` output are version-pinned;
   - it never creates `activities` rows and never sends invitations.
5. Operator endpoints under `/api/operator`:
   `POST /circles/{id}/activity-plan`, `GET /activity-plans/{id}`,
   `GET /circles/{id}/activity-plans`,
   `POST /activity-plans/{id}/decision`.
6. Audit events: `activity_plan.requested`, `activity_plan.generated`,
   `activity_plan.failed`, `activity_plan.decision.{approved|rejected|edited}`.
7. Tests for fake-client persistence, prompt-payload privacy, missing
   API-key failure, no-side-effects on activities/invitations,
   failure-path persistence, operator-decision auditing, and the FastAPI
   endpoints.
8. `python -m app.api` loads repo-root `.env` / `.emv` files and wires
   `OpenAIChatLLMClient()` into `create_app`.

**Feature 8: Behavioral signals + matching orchestration service layer.**

The deterministic activity-ranking engine (feature 5), deterministic
circle/group matching engine (feature 6), and the first behavior-aware
workflow slice (feature 8) are built. The v2 path is opt-in via
`model_version="v2"` and `fair_grouping=True`, so v1 behavior remains stable.

Implemented:
1. Safe behavioral signals from invitations, attendance, resident feedback,
   and safety flags with exponential decay (`0.95^weeks`) and bounded boosts.
2. V2 activity ranking components for behavior and comfort alignment.
3. Fair circle grouping with priority for less-served residents, score-spread
   penalty, and persisted eligible-but-unmatched explanations.
4. `MatchingWorkflowService` for referral acceptance → v2 ranking → fair circle
   matching, operator decision audit rows, and approved-circle invitation sends.
5. Tests for behavioral scoring artifacts, fair grouping unmatched residents,
   and audit rows around invitation promotion.

Remaining:
1. Expose thin HTTP/API routes for the matching workflow service.
2. Expand operator-dashboard views for proposed circles, unmatched residents,
   and audit explanations.
3. Production deployments still need secret management for `OPENAI_API_KEY`
   (local development can use repo-root `.env`; do not commit it).

Group-fit weights in use (feature 6, sum to 1.0):
- `template_fit`: 0.50
- `availability_density`: 0.20 (saturates at 3 shared buckets)
- `interest_overlap`: 0.15 (saturates at 3 shared interest/theme keys)
- `group_size_comfort`: 0.10
- `social_energy_consistency`: 0.05

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

V2 behavior model:
- safe positive behavior is capped and decayed before boosting
  `activity_pref:<code>` and `family:<value>` features
- declined/expired invitations, no-shows, negative feedback, and safety flags
  dampen repeated templates/families without creating public resident scores

---

## 11. Commit history conventions

Current branch `fer/features` history:
```
f314946 feat: add deterministic circle/group matching engine v1
25238a4 chore: remove throwaway matching inspector UI
842b397 Merge jose GP onboarding API into feature branch
ac3a361 docs: record matching inspector commit hash
abe8a25 chore: add throwaway matching inspector UI
2b6659a feat: expand API to full coverage across all repositories
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
- Do not commit `backend/civiccircles.db`, `.venv-libs/`, or `__pycache__`.
- Do not combine multiple features in a single commit.
- Do not add silent fallbacks that mask matching errors; matching must be auditable.
- Do not replace the verification stub with live register calls without an explicit integration decision.

---

## 13. Quick onboarding checklist for a new agent

1. Read this file.
2. Skim `backend/README.md`.
3. Run the test suite — it should be all green.
4. Run `python3 backend/scripts/seed_activity_catalog.py` to populate the catalog.
5. Inspect `backend/data/activity_catalog.json` to understand the activity space.
6. Implement the next feature listed in section 10.
