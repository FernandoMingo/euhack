"""
FastAPI app for CivicCircles.

Routers are organized by resource. Mounting happens here so the router
modules stay focused on request/response shape and business calls.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    activities,
    consents,
    demo,
    health,
    invitations,
    operator,
    professionals,
    referrals,
    residents,
    templates,
)
from app.db import DEFAULT_DB_PATH, init_db


def create_app(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    initialize_db: bool = True,
) -> FastAPI:
    app = FastAPI(title="CivicCircles API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.db_path = Path(db_path)
    if initialize_db:
        init_db(db_path=db_path)

    app.include_router(health.router)
    app.include_router(professionals.router)
    app.include_router(referrals.router)
    app.include_router(residents.router)
    app.include_router(templates.router)
    app.include_router(activities.venues_router)
    app.include_router(activities.hosts_router)
    app.include_router(activities.activities_router)
    app.include_router(activities.circles_router)
    app.include_router(invitations.router)
    app.include_router(consents.router)
    app.include_router(operator.router)
    app.include_router(demo.router)

    return app


# Uvicorn factory alias: `uvicorn app.api.main:app --factory --reload`.
app = create_app
