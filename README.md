# CivicCircles Prototype

Calm resident map, GP-created lightweight profile, activity matching, Circle Reveal after check-in, reflection storage, professional dashboard, operator approval dashboard.

## Scope

- No real authentication.
- No real email, payments, clinical records, or production AI.
- No chat, inbox, feed, or people marketplace.
- Matching ranks activity fit. Does not rank people by social value.

## Structure

```text
backend/            ← friend backend (FastAPI + sqlite3 repos)
  app/api/main.py
  app/api/routers/demo.py   ← frontend-friendly demo endpoints
  app/repositories/
  app/matching/
  sql/
  init_db.py
  seed_demo.py
old_codex_backend/  ← original Codex SQLModel backend (archived)
frontend/           ← Next.js TypeScript Tailwind app
  app/
  components/ResidentMapExperience.tsx
  lib/api.ts
```

## Backend Setup

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

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Environment variables (optional — create `frontend/.env.local`):

```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_MAPBOX_TOKEN=pk....
```

Frontend runs at `http://localhost:3000`.

## Demo Flow

1. Open `http://localhost:3000`.
2. Sofia sees multiple activity markers on the Amsterdam map.
3. Tap a pin → invitation card opens.
4. **Join** — accept the invitation.
5. Allow browser location. The demo creates one **Calm Check-in Test** activity at Sofia's initial location.
6. **Check in** unlocks when Sofia is within 50m.
7. Circle Reveal shows limited attendee cards (first name + icebreaker).
8. Open Reflection and save Sofia's post-event feedback.
9. Open `/professional` to view/edit Sofia's preferences.
10. Open `/operator` to review the separate operator dashboard.
11. Click the **Profile** icon (top-right or nav tab) to edit preferences directly.

## Activity Catalog Preferences

Profile preference choices are finite options loaded from `backend/data/activity_catalog.json`.
If the friend backend catalog changes, copy the updated file into that path before seeding/running.

## API Smoke Checks

```bash
curl http://127.0.0.1:8000/api/resident/me
curl http://127.0.0.1:8000/api/resident/invitations
curl http://127.0.0.1:8000/api/catalog/preferences
curl -X POST http://127.0.0.1:8000/api/demo/nearby-activity \
  -H "Content-Type: application/json" \
  -d '{"lat":51.9225,"lng":4.47917}'
curl -X POST http://127.0.0.1:8000/api/activities/act-photo-walk/check-in
curl http://127.0.0.1:8000/api/activities/act-photo-walk/circle-reveal
```

## Seeded Demo Data

- **Resident**: Sofia (`sofia-001`) — Oud-West, Amsterdam.
- **Professional**: Dr. Anna Vermeer, GP, Oud-West Health Center.
- **Activities**: Calm Photography Walk (Vondelpark), Quiet Museum Morning (Rijksmuseum), Evening Board Games (OBA), Slow Coffee & Sketching (Café De Wester).
- **Circle members**: Lena, Tom, Mara, Felix.
- All activities visible on map with distinct coordinates.
