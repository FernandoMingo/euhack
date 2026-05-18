# CivicCircles Prototype

CivicCircles is an AI-powered social prescribing platform that helps cities reduce loneliness through small, low-pressure, offline activities.

This repository now contains the current SQLite/FastAPI backend implementation and the frontend demo surface from `origin/main`.

## Scope

- No real authentication.
- No real email, payments, clinical records, or production AI.
- No chat, inbox, feed, public attendee browsing, or people marketplace.
- Matching must remain explainable and must not rank people by social value.

## Structure

```text
backend/
  app/api/main.py
  app/db.py
  app/seed.py
  app/matching/
  app/repositories/
frontend/
  app/
  components/
  lib/api.ts
```

## Backend Setup

```bash
python3 -m pip install -r backend/requirements.txt
python3 backend/init_db.py
python3 backend/scripts/seed_activity_catalog.py
PYTHONPATH="$(pwd)/backend" python3 -m app.api --host 127.0.0.1 --port 8000
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
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/templates
```

## Documentation

- Backend data layer docs: `backend/README.md`
- Product specification: `civiccircles_project_spec.md`
