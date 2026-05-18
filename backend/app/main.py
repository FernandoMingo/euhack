from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from app.api.ai import router as ai_router
from app.api.operator import router as operator_router
from app.api.professional import router as professional_router
from app.api.resident import router as resident_router
from app.core.request_context import RequestContextMiddleware
from app.core.response import error_response, ok_response
from app.db import Session, create_db_and_tables, engine
from app.seed.seed_data import seed_demo_data

app = FastAPI(
    title="CivicCircles Backend",
    description="FastAPI backend for CivicCircles hackathon prototype",
    version="0.1.0",
    openapi_tags=[
        {"name": "resident", "description": "Resident APIs"},
        {"name": "professional", "description": "Trusted professional APIs"},
        {"name": "operator", "description": "City operator APIs"},
        {"name": "ai", "description": "Deterministic AI simulation APIs"},
    ],
)

app.add_middleware(RequestContextMiddleware)


@app.on_event("startup")
def startup_event() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed_demo_data(session)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    reason_code = "HTTP_ERROR"
    if exc.status_code == 404:
        reason_code = "NOT_FOUND"
    if exc.status_code == 403:
        reason_code = "FORBIDDEN"
    if exc.status_code == 401:
        reason_code = "UNAUTHORIZED"
    return error_response(str(exc.detail), request, reason_code=reason_code, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return error_response(str(exc), request, reason_code="INTERNAL_ERROR", status_code=500)


@app.get("/health", tags=["system"])
def health(request: Request):
    return ok_response({"status": "healthy"}, request)


app.include_router(resident_router)
app.include_router(professional_router)
app.include_router(operator_router)
app.include_router(ai_router)
