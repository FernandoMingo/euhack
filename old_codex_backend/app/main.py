from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.db import create_db_and_tables, engine
from app.routes.ai import router as ai_router
from app.routes.operator import router as operator_router
from app.routes.professional import router as professional_router
from app.routes.resident import router as resident_router
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    with Session(engine) as session:
        seed_demo_data(session)
    yield

app = FastAPI(
    title="CivicCircles Prototype API",
    description="Deterministic FastAPI + SQLite prototype for low-pressure social prescribing.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


app.include_router(resident_router)
app.include_router(professional_router)
app.include_router(operator_router)
app.include_router(ai_router)
