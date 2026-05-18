# CivicCircles Prototype

First working CivicCircles demo: calm resident map, GP-created lightweight profile, deterministic activity matching, Circle Reveal after check-in, reflection storage, professional dashboard, and operator approval dashboard.

## Scope

- No real authentication.
- No real email, payments, clinical records, or production AI.
- No chat, inbox, feed, public attendee browsing, or people marketplace.
- Matching ranks activity fit only. It does not rank people by social value.

## Structure

```text
backend/
  app/main.py
  app/db.py
  app/models.py
  app/seed.py
  app/matching.py
  app/routes/
frontend/
  app/
  components/
  lib/api.ts
```

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m app.seed --reset
uvicorn app.main:app --reload
```

Backend runs at `http://127.0.0.1:8000`. If that port is occupied, use another port and set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`.

## Frontend Setup

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

`NEXT_PUBLIC_MAPBOX_TOKEN` is optional. If omitted, the resident screen uses the built-in static fallback map. If present, Mapbox renders the map and the 2D/3D toggle changes pitch and bearing.

## Demo Flow

1. Open `http://localhost:3000`.
2. Sofia sees the Calm Photography Walk on the map.
3. Open the invitation card.
4. Accept the invitation.
5. Simulate arrival.
6. Circle Reveal unlocks limited attendee cards.
7. Open Reflection and save Sofia’s post-event reflection.
8. Open `/professional` to edit Sofia’s lightweight preferences.
9. Open `/operator` to review the anonymous graph, ranking, audit checklist, and approve/reject the proposal.

Resident and operator surfaces are intentionally separate:

- Resident view: `http://localhost:3000`
- Operator view: `http://localhost:3000/operator`

## Seeded Demo Data

- Resident: Sofia, referred by GP Dr. Anna Vermeer.
- Main activity: Calm Photography Walk, Saturday 10:30, Vondelpark.
- Circle: Sofia plus Resident A-D.
- Compatibility signals: Saturday morning, calm outdoor preference, photography/parks overlap, small group comfort, step-free route, alcohol-free preference.

## API Smoke Checks

```bash
curl http://127.0.0.1:8000/api/resident/me
curl http://127.0.0.1:8000/api/resident/invitations
curl -X POST http://127.0.0.1:8000/api/ai/rank-activities \
  -H "Content-Type: application/json" \
  -d '{"circle_id":"circle_photo_walk"}'
```
