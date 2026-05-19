# CivicCircles

> **Social prescribing, powered by AI, without the social network.**

CivicCircles is an AI-powered social prescribing platform that helps cities reduce loneliness through small, low-pressure, offline activities. It is built for a 24-hour hackathon — the full product specification lives in [`civiccircles_project_spec.md`](civiccircles_project_spec.md).

---

## The one-sentence pitch

**CivicCircles helps cities fight loneliness by turning trusted professional referrals into AI-organized, low-pressure offline activities where compatible residents can meet safely.**

---

## The problem

Cities are dense with people, but many residents still experience isolation. Existing social platforms often make the problem worse by adding performance pressure, comparison, superficial browsing, rejection, and endless digital interaction.

Most people who are lonely do not need another app to scroll. They need a low-pressure path into real-world social contact. Common barriers include:

- Not knowing where to start.
- Anxiety around initiating social contact.
- Discomfort with messaging strangers.
- Lack of trust in open social platforms.
- Events that are too large, generic, loud, late, expensive, or intimidating.
- Lack of continuity after one-off events.
- Difficulty finding people with compatible interests and social comfort levels.
- Shame around explicitly joining a "loneliness" group.

CivicCircles removes the hardest parts: searching, choosing, messaging, and initiating.

---

## The core insight

The people who most need connection are often the least likely to initiate it themselves.

So the product should not ask users to behave like power users of a social app. It should create a supportive path from a trusted referral to real-world participation.

---

## What CivicCircles is — and isn't

**CivicCircles is:**

- A consent-based social prescribing platform.
- A city activity coordination system.
- An offline-first matching engine.
- A low-pressure invitation system.
- A human-approved AI recommendation platform.
- A privacy-first bridge between care systems and civic life.

**CivicCircles is not:**

- A chatbot.
- A dating app.
- A social network.
- A friend-swiping app.
- A feed.
- A mental health diagnosis tool.
- A replacement for therapy.
- A public event marketplace.
- A platform for browsing vulnerable people.
- A leaderboard for social success.

---

## How it works

```text
Trusted professional referral
        │
        ▼
Consent + lightweight social profile
        │
        ▼
AI forms compatible small group  ◄── deterministic + explainable
        │
        ▼
AI proposes a real-world activity ◄── LLM-backed, operator-reviewable
        │
        ▼
City operator approves / edits / rejects
        │
        ▼
Calm invitation in resident inbox + email
        │
        ▼
Resident RSVPs (or brings a friend with a Companion Pass)
        │
        ▼
Resident arrives, checks in, **Circle Reveal** unlocks
        │
        ▼
30-second post-event reflection → feeds the next recommendation
```

The resident experience is intentionally minimal: a paper-like city map, a profile icon, and a few calm invitation cards. All the complexity — matching, safety, approval, and audit logic — lives in separate professional and city/operator dashboards.

---

## Core product principles

1. **Activity first, people second, identity last.** Users see the activity first, then the group vibe, and only later the identities of attendees.
2. **Offline first.** Connection begins in the real world, not through online messaging.
3. **Minimal for residents, transparent for operators.** Simple resident UI, fully auditable operator dashboards.
4. **Consent first.** Every profile is created through explicit consent; users can pause or withdraw anytime.
5. **No clinical data in matching.** No diagnoses, therapy notes, or medication history — ever.
6. **Human approval.** AI proposes; humans approve.
7. **No social ranking of people.** The system ranks activity fit, not human worth.
8. **Gentle continuity.** After an activity, suggest a natural next step — not random events.
9. **Private progress, not gamification.** No leaderboards, social scores, or points for making friends.
10. **Explainability over opacity.** Every AI recommendation produces a short human-readable rationale and an auditable structured rationale.

---

## Key product concepts

### Companion Pass

A resident can bring one trusted person to an activity to reduce first-event anxiety. The guest sees only event logistics and does not access the full platform unless they sign up properly.

### Common Ground Preview

Before the event, the resident sees anonymized group-level information — group size, shared interests, pace, host presence — but no names or photos yet.

### Circle Reveal

When the resident has RSVP'd, is within the event time window, is near the meeting point, and actively checks in, the app unlocks short attendee cards: first name, optional avatar, short bio, common ground, optional icebreaker. This reduces arrival awkwardness without enabling pre-event browsing.

### Gentle Continuity

After each activity, CivicCircles recommends the next safest step: a similar activity, a recurring circle, attending again with someone they've met, or a nearby low-pressure alternative.

### 30-Second Reflection

A short post-event feedback flow that helps the AI improve recommendations **without** asking users to rate each other. It asks about the activity, the group comfort, and whether the resident would do something similar again.

---

## Who it's for

- **Residents** — newcomers, remote workers, elderly residents, international students, recently-divorced people, immigrants, caregivers, people recovering from burnout, anyone referred by a GP or psychologist, anyone who wants to reconnect with local community life.
- **Trusted professionals** — GPs, psychologists, therapists, social workers, university counselors, elder-care coordinators, community health workers, NGO workers, municipal loneliness prevention workers.
- **City operators and local organizers** — municipality workers, community center coordinators, library program managers, sports club operators, museum partners, parks departments, volunteer coordinators, NGO operators.
- **Activity hosts** — volunteers, city workers, community organizers, venue employees, or trained CivicCircles hosts who anchor the real-world experience.

---

## Privacy and safety, by design

These are hard guarantees, baked into the schema, the matching engine, and every audit row:

- **No clinical data anywhere.** No diagnoses, therapy notes, medications.
- **No public ranking of people.** The system may rank activity fit or group fit, but never people's social value.
- **No "likeability" or social score exposed to users.** Internal peer-rating signals exist only for matching/safety quality, are never displayed to other residents, and only thresholded aggregates influence matching.
- **AI proposes; humans approve.** Every activity proposal flows through an operator decision.
- **Every AI recommendation produces a rationale.** Human-readable + structured, audit-logged.
- **Attendee identities are revealed only at arrival** after an active check-in.
- **No pre-event direct messaging.**
- **Reporting is always available.** Safety reports route to operators with clear escalation levels.

---

## Demo persona — Sofia

Sofia is 29, moved to Amsterdam six months ago, works remotely, and has been feeling isolated. She tells her GP she wants to meet people but does not want dating apps, social media, or large events.

Her GP offers CivicCircles. Sofia consents.

Her lightweight profile:

- Interests: photography, parks, coffee, museums.
- Availability: Saturday mornings.
- Comfort: small groups, calm settings.
- Avoid: alcohol, loud venues, late nights.
- Accessibility: step-free routes.
- Location radius: 3 km.
- Companion Pass: allowed.

The AI groups Sofia with four other residents and proposes a calm photography walk. The city operator approves. Sofia receives a simple invitation, accepts, arrives at Vondelpark, taps "Check in" — and Circle Reveal unlocks short cards for the four other people standing nearby.

After the walk she reports feeling better. The system gently suggests a community garden visit with a similar group next week.

---

## Judge-friendly talking points

> CivicCircles is not a social network. It is a social prescribing engine.

> The user does not browse people. The city helps them receive the right invitation at the right time.

> The AI ranks activity fit, not human worth.

> Every recommendation has an auditable decision trail.

> We deliberately keep the resident UI minimal because loneliness is not solved by more screen time.

> Connection starts offline, but the app makes the first moment less scary.

> AI proposes, humans approve.

> We do not reward people for making friends. We support the courage to show up.

---

## North star metric

> **Number of residents who attend at least two comfortable offline activities within 30 days.**

This captures repeated offline contact without turning friendship into a metric.

---

# Technical Implementation

Everything below is the engineering view of the hackathon prototype. The product narrative above is the source of truth for *why*; this section is the source of truth for *how it runs*.

## Scope of the prototype

- No chat, inbox-as-feed, or people marketplace.
- Matching ranks activity fit. It does not rank people by social value.
- The backend ships deterministic behavioral/group matching plus optional LLM-backed activity planning for operators.

## Tech stack

- **Backend:** Python 3.10+, FastAPI, Pydantic, `sqlite3` (stdlib), plain dataclasses (no ORM).
- **Migrations:** plain `.sql` files in `backend/sql/`, applied in filename order by `backend/init_db.py`.
- **Tests:** `unittest` + FastAPI `TestClient`.
- **Matching engine:** deterministic vectorizer + cosine scoring + behavioral signals (v2), plus fair circle grouping.
- **LLM layer:** OpenAI Responses API via `OpenAIChatLLMClient`, wired in `python -m app.api` from `OPENAI_API_KEY` in the repo-root `.env`. The Responses API runs with web search enabled so activity plans can suggest real Rotterdam venues. If the key is missing, only the planning endpoints respond with HTTP 503 — the rest of the API keeps working.
- **Email layer:** pluggable `EmailClient` chosen by `build_email_client_from_env()`. We run on Gmail SMTP with an App Password (`civiccirclenl@gmail.com`) so real invitations land in real inboxes during the demo. `ResendEmailClient` and a default no-send `QueuedEmailClient` are still available as fallbacks.
- **Frontend:** Next.js + TypeScript + Tailwind.

## Repository layout

```text
euhack/
├── AGENTS.md                          # source-of-truth context for AI agents / new contributors
├── civiccircles_project_spec.md       # full product spec
├── backend/                           # FastAPI + sqlite3 backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── main.py                # FastAPI app factory
│   │   │   ├── routers/               # health, professionals, referrals, residents,
│   │   │   │                          # templates, activities, invitations, consents,
│   │   │   │                          # inbox, operator, demo
│   │   │   ├── schemas.py             # Pydantic request/response models
│   │   │   └── deps.py                # per-request DB connection
│   │   ├── matching/                  # vectorizer, scoring, engine, grouping, behavioral, explain
│   │   ├── services/                  # onboarding, matching workflow, activity planning,
│   │   │                              # invitation inbox, LLM client, email client, verification
│   │   ├── repositories/              # one repository per table cluster
│   │   ├── dataclasses.py             # all domain dataclasses
│   │   ├── db.py                      # connect + init_db with migration scan
│   │   ├── seed.py                    # activity-catalog loader
│   │   └── logging_config.py
│   ├── data/activity_catalog.json     # 131 seedable activity templates
│   ├── scripts/seed_activity_catalog.py
│   ├── sql/                           # 001…006 migrations
│   ├── tests/                         # unittest + TestClient suites
│   ├── init_db.py                     # CLI: apply all sql/*.sql migrations
│   ├── seed_demo.py                   # seed Sofia + 4 activities + circles + invitations
│   └── requirements.txt
├── old_codex_backend/                 # archived original SQLModel backend
└── frontend/                          # Next.js TypeScript Tailwind app
    ├── app/
    ├── components/ResidentMapExperience.tsx
    └── lib/api.ts
```

## Backend setup

```bash
cd backend
pip install -r requirements.txt

# Initialise DB (creates civiccircles.db)
python3 init_db.py

# Seed demo data (Sofia + 4 activities + circles + invitations)
python3 seed_demo.py

# Run
uvicorn app.api.main:app --factory --reload
# or
python3 -m app.api
```

Backend runs at `http://127.0.0.1:8000`.

### Backend feature notes

- The frontend demo uses compatibility routes in `backend/app/api/routers/demo.py`.
- Operator APIs expose matching workflow, proposed circles, audit events, invitation promotion, and activity plan review endpoints.
- `python -m app.api` auto-loads `.env` (and `.emv` as a typo-tolerant alias) from the repo root, then constructs `OpenAIChatLLMClient()` and calls `build_email_client_from_env()` for outbound email. The DB defaults to `backend/civiccircles.db` (`DEFAULT_DB_PATH`).

### How we configure OpenAI and email

The demo runs against real OpenAI and a real Gmail SMTP sender. Everything lives in a single repo-root `.env` file that `python -m app.api` reads on startup:

```bash
# OpenAI — used by OpenAIChatLLMClient for LLM-backed activity planning
# (Responses API, web search enabled, model defaults set in llm_client.py)
OPENAI_API_KEY=sk-proj-...

# Gmail SMTP via App Password — used by build_email_client_from_env()
# This is the actual CivicCircles demo sender.
# Account: civiccirclenl@gmail.com
# (2-Step Verification on the account + App Password generated at
#  https://myaccount.google.com/apppasswords)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=civiccirclenl@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_FROM=CivicCircles <civiccirclenl@gmail.com>
```

What this gets you:

- `OpenAIChatLLMClient()` picks up `OPENAI_API_KEY` and `ActivityPlanningService` produces real Rotterdam venue suggestions for operators to review.
- `build_email_client_from_env()` sees `SMTP_HOST` + `SMTP_USERNAME` + `SMTP_PASSWORD` (+ optional `EMAIL_FROM`) and returns an `SMTPEmailClient`. When an operator promotes an approved circle to invitations, residents get a real email from `civiccirclenl@gmail.com` (in addition to the resident-inbox item and the `outbound_email_messages` audit row).
- If you omit the SMTP block, `build_email_client_from_env()` returns `None` and the CLI logs a warning; invitation rows stay `queued` in `outbound_email_messages` so the rest of the demo still works.
- If you omit `OPENAI_API_KEY`, every endpoint still runs but the activity-planning endpoints respond with HTTP 503.

`ResendEmailClient` is also wired in (`RESEND_API_KEY` + `EMAIL_FROM`) as a fallback for production-style sender domains; SMTP takes priority when both are set.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Environment variables (optional — create `frontend/.env.local`):

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_MAPBOX_TOKEN=pk....
```

Frontend runs at `http://localhost:3000`.

## Demo flow

1. Open `http://localhost:3000`.
2. Sofia sees multiple activity markers on the Amsterdam map.
3. Tap a pin → invitation card opens.
4. **Join** — accept the invitation.
5. Allow browser location. The demo creates one **Calm Check-in Test** activity at Sofia's initial location.
6. **Check in** unlocks when Sofia is within 50 m.
7. Circle Reveal shows limited attendee cards (first name + icebreaker).
8. Open Reflection and save Sofia's post-event feedback.
9. Open `/professional` to view/edit Sofia's preferences.
10. Open `/operator` to review the separate operator dashboard.
11. Click the **Profile** icon (top-right or nav tab) to edit preferences directly.

## Activity catalog preferences

Profile preference choices are finite options loaded from `backend/data/activity_catalog.json` (131 templates across families like `walks_outdoor`, `food_drink`, `pubs_social`, `sports_casual`, `arts_crafts`, `cultural`, `photography`, `tabletop_games`, `music`, `wellness_mind_body`, `learning_workshops`, `gardening_nature`, `volunteering_civic`, `repair_diy`, …). If the backend catalog changes, copy the updated file into that path before seeding/running.

## API smoke checks

```bash
curl http://127.0.0.1:8000/api/resident/me
curl http://127.0.0.1:8000/api/resident/invitations
curl http://127.0.0.1:8000/api/catalog/preferences
curl -X POST http://127.0.0.1:8000/api/demo/nearby-activity \
  -H "Content-Type: application/json" \
  -d '{"lat":51.9225,"lng":4.47917}'
curl http://127.0.0.1:8000/api/operator/proposed-circles
curl http://127.0.0.1:8000/api/operator/audit-events
curl -X POST http://127.0.0.1:8000/api/activities/act-photo-walk/check-in
curl http://127.0.0.1:8000/api/activities/act-photo-walk/circle-reveal
```

## Run the test suite

From the repo root:

```bash
PYTHONPATH="$(pwd)/backend" python3 -m unittest discover -s backend/tests -p "test_*.py"
```

## Seeded demo data

- **Resident:** Sofia (`sofia-001`) — Oud-West, Amsterdam.
- **Professional:** Dr. Anna Vermeer, GP, Oud-West Health Center.
- **Activities:** Calm Photography Walk (Vondelpark), Quiet Museum Morning (Rijksmuseum), Evening Board Games (OBA), Slow Coffee & Sketching (Café De Wester).
- **Circle members:** Lena, Tom, Mara, Felix.
- All activities visible on the map with distinct coordinates.

---

For the full product narrative — user lifecycles, dashboard specs, matching algorithm, data model, API spec, safety model, retention strategy, demo script, and pitch-deck structure — see [`civiccircles_project_spec.md`](civiccircles_project_spec.md).
