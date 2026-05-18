# CivicCircles Python Backend

FastAPI + SQLite backend implementing the CivicCircles project specification for prototype and demo flows.

## Run locally

```bash
python3 -m pip install --target .deps fastapi uvicorn sqlmodel pydantic
PYTHONPATH=".deps:." uvicorn app.main:app --reload
```

## Run tests

```bash
python3 -m pip install --target .deps fastapi uvicorn sqlmodel pydantic pytest httpx
PYTHONPATH=".deps:." pytest tests
```

### Full suite (recommended)

```bash
bash scripts/run_full_test_suite.sh
```

This runs:
- acceptance + unit + security/negative + determinism tests
- coverage report (`coverage.xml` plus terminal missing-lines output)
- end-to-end demo scenario runner checks

## Generate fake users and watch full flow

Run a population simulation that:
- creates fake residents with consent + profile data
- runs ranking, explanation, proposal generation, and operator approval
- sends and accepts invitations per cohort
- writes reports showing matches, top suggested activities, scores, and rationale signals

```bash
PYTHONPATH=".deps:." python scripts/simulate_population_flow.py --users 30 --group-size 5 --seed 42
```

Outputs are written to `backend/reports/` as:
- `simulation_<timestamp>.json` (full machine-readable result)
- `simulation_<timestamp>.md` (easy-to-read summary)

## API groups
- `resident`: invitations, RSVP, check-in, circle reveal, feedback, connection request
- `professional`: signup, referral, profile creation, preference updates
- `operator`: proposal review actions, matching graph, safety/privacy audit, equity
- `ai`: deterministic circle generation, ranking, proposal generation, explainability, preference updates

## Notes
- Uses mock role headers (`x-actor-role`, `x-actor-id`) by design for prototype speed.
- Response contract is standardized as `{ ok, data, error, meta }`.
- Demo seed data includes Sofia scenario from the spec.
