from __future__ import annotations

from sqlmodel import Session, select

from app.db import engine
from app.models import DecisionLog


def _rank(client, headers):
    response = client.post(
        "/api/ai/rank-activities",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
    )
    assert response.status_code == 200
    return response.json()["data"]["ranked_activities"]


def test_rank_activities_is_deterministic_for_same_input(client, headers):
    first = _rank(client, headers)
    second = _rank(client, headers)
    assert [row["activity_id"] for row in first] == [row["activity_id"] for row in second]
    assert [row["fit_score"] for row in first] == [row["fit_score"] for row in second]


def test_explain_match_returns_expected_shape(client, headers):
    response = client.post(
        "/api/ai/explain-match",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"], "activity_id": "activity_001"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "top_positive_signals" in data
    assert "hard_constraints_passed" in data
    assert "alternative_activities_considered" in data
    assert data["recommended_activity"] == "activity_001"


def test_decision_logs_are_written_for_ai_endpoints(client, headers):
    client.post(
        "/api/ai/generate-circles",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
    )
    client.post(
        "/api/ai/rank-activities",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
    )
    with Session(engine) as session:
        logs = session.exec(select(DecisionLog).where(DecisionLog.actor_id == "operator_001")).all()
    endpoints = {entry.endpoint for entry in logs}
    assert "generate-circles" in endpoints
    assert "rank-activities" in endpoints
