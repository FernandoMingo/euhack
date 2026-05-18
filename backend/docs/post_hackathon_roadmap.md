# Post-Hackathon Backend Roadmap

## Goal
Evolve the prototype FastAPI + SQLite backend into a pilot-ready service with stronger reliability, security, and operational controls.

## 1) Database Migration Path (SQLite -> Postgres)
- Keep SQLModel model definitions database-agnostic and remove SQLite-only assumptions.
- Add Alembic and baseline migration generated from current schema.
- Introduce environment-configured DSN (`DATABASE_URL`) and migration commands for local and CI.
- Run dual-environment checks: SQLite for lightweight dev, Postgres for staging/prod.

## 2) Background Jobs
- Add a worker process (e.g., Celery + Redis or Dramatiq + Redis) for:
  - periodic activity ranking refresh,
  - batch recommendation regeneration,
  - delayed reminder sends,
  - nightly equity snapshots.
- Keep API request path synchronous only for user-visible actions; move heavy recomputation to worker queues.
- Add idempotency keys for replay-safe queued jobs.

## 3) Production Authentication and Authorization
- Replace mock actor headers with OAuth2/JWT and rotating signing keys.
- Introduce role claims (`resident`, `professional`, `operator`, `host`) and per-endpoint policy checks.
- Add professional verification workflow and approval state transitions.
- Implement consent revocation flow that immediately removes residents from future matching batches.

## 4) Safety and Incident Operations
- Add incident model and lifecycle (`new`, `triaged`, `investigating`, `closed`).
- Build escalation routing for level 3/4 reports with paging hooks.
- Add pairwise blocklist enforcement to prevent rematching reported pairs.
- Add immutable incident audit trail for operator accountability.

## 5) Observability and Reliability
- Structured logs with request IDs and endpoint latency.
- Metrics: invitation acceptance, attendance, safety reports, ranking latency, queue lag.
- Tracing for service boundaries (API -> matching -> persistence -> worker).
- Error budgets and alerts for critical flows (check-in, reveal gating, proposal approval).

## 6) Delivery Milestones
- Milestone A: Postgres + Alembic + CI migration checks.
- Milestone B: Worker queue + asynchronous ranking refresh.
- Milestone C: AuthN/AuthZ replacement and consent revocation.
- Milestone D: Incident ops and observability hardening.
