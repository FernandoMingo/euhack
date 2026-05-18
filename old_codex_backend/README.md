# CivicCircles Backend

FastAPI + SQLite prototype API for the Sofia demo flow.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m app.seed --reset
uvicorn app.main:app --reload
```

## Key Endpoints

- `GET /api/resident/me`
- `GET /api/resident/invitations`
- `POST /api/invitations/{id}/accept`
- `POST /api/invitations/{id}/decline`
- `POST /api/activities/{id}/check-in`
- `GET /api/activities/{id}/circle-reveal`
- `POST /api/activities/{id}/feedback`
- `GET /api/professionals/referrals`
- `PATCH /api/residents/{id}/preferences`
- `GET /api/operator/proposals`
- `POST /api/operator/proposals/{id}/approve`
- `POST /api/operator/proposals/{id}/reject`
- `GET /api/operator/matching-graph/{circleId}`
- `GET /api/operator/audit/{activityId}`
- `POST /api/ai/rank-activities`
- `POST /api/ai/explain-match`

No auth headers are needed. Demo resident is Sofia.
