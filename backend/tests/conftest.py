from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import DB_PATH, engine
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    engine.dispose()
    if DB_PATH.exists():
        DB_PATH.unlink()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def headers() -> dict[str, dict[str, str]]:
    return {
        "operator": {"x-actor-role": "operator", "x-actor-id": "operator_001"},
        "resident": {"x-actor-role": "resident", "x-actor-id": "resident_123"},
        "professional": {"x-actor-role": "professional", "x-actor-id": "professional_456"},
    }
