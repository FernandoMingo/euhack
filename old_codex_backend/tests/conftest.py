from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import engine, reset_db
from app.main import app
from app.seed import seed_demo_data
from sqlmodel import Session


@pytest.fixture()
def client() -> TestClient:
    engine.dispose()
    reset_db()
    with Session(engine) as session:
        seed_demo_data(session)
    with TestClient(app) as test_client:
        yield test_client
