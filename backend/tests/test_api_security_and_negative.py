from __future__ import annotations

from sqlmodel import Session, delete

from app.db import engine
from app.models import ConsentRecord, Invitation, Resident


def test_missing_headers_returns_unauthorized(client):
    response = client.get("/api/resident/me")
    body = response.json()
    assert response.status_code == 401
    assert body["ok"] is False
    assert body["error"]["reason_code"] == "UNAUTHORIZED"


def test_wrong_role_returns_forbidden(client, headers):
    response = client.get("/api/operator/proposals", headers=headers["resident"])
    body = response.json()
    assert response.status_code == 403
    assert body["ok"] is False
    assert body["error"]["reason_code"] == "FORBIDDEN"


def test_resident_cannot_accept_other_resident_invitation(client, headers):
    with Session(engine) as session:
        invitation = Invitation(
            id="invite_activity_001_other_resident",
            resident_id="resident_234",
            activity_id="activity_001",
            status="sent",
        )
        session.merge(invitation)
        session.commit()
    response = client.post("/api/invitations/invite_activity_001_other_resident/accept", headers=headers["resident"])
    assert response.status_code == 404


def test_referral_requires_consent(client, headers):
    response = client.post(
        "/api/residents/referral",
        headers=headers["professional"],
        json={
            "resident_id": "resident_911",
            "first_name": "No Consent",
            "email": "noconsent@example.com",
            "preferred_language": "English",
            "consent_given": False,
            "consent_scope": [],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Consent is required to create referral"


def test_profile_update_without_active_consent_forbidden(client, headers):
    with Session(engine) as session:
        resident = Resident(id="resident_777", first_name="Revoked", email="revoked@example.com")
        session.merge(resident)
        session.add(
            ConsentRecord(
                id="consent_revoked",
                resident_id="resident_777",
                professional_id="professional_456",
                consent_scope=["use_profile_for_activity_matching"],
                revoked_at=resident.created_at,
            )
        )
        session.commit()
    response = client.post(
        "/api/residents/resident_777/profile",
        headers=headers["professional"],
        json={
            "approx_location": {"city": "Amsterdam"},
            "location_radius_km": 3,
            "interests": ["photography"],
            "activity_preferences": ["walks"],
            "availability": ["Saturday morning"],
            "social_comfort": "small_group_low_pressure",
            "preferred_group_size": {"min": 3, "max": 5},
            "accessibility_needs": [],
            "cost_sensitivity": "free_or_low_cost",
            "avoid": [],
            "profile_visibility": {"first_name": True},
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["reason_code"] == "FORBIDDEN"


def test_patch_preferences_strips_sensitive_fields(client, headers):
    response = client.patch(
        "/api/residents/resident_123/preferences",
        headers=headers["professional"],
        json={"preferences": {"diagnosis": "x", "medical_history": "y", "quiet_venues_only": True}},
    )
    assert response.status_code == 200
    prefs = response.json()["data"]["preferences"]
    assert "diagnosis" not in prefs
    assert "medical_history" not in prefs
    assert prefs["quiet_venues_only"] is True


def test_connection_request_requires_coattendance(client, headers):
    response = client.post(
        "/api/connections/request",
        headers=headers["resident"],
        json={"to_resident_id": "resident_999", "activity_id": "activity_001"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["reason_code"] == "FORBIDDEN"


def test_nonexistent_resource_returns_not_found_reason_code(client, headers):
    response = client.get("/api/operator/proposals/does_not_exist", headers=headers["operator"])
    assert response.status_code == 404
    assert response.json()["error"]["reason_code"] == "NOT_FOUND"


def test_generate_circles_rejects_too_few_residents(client, headers):
    response = client.post(
        "/api/ai/generate-circles",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234"]},
    )
    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_generate_circles_requires_matching_consent(client, headers):
    with Session(engine) as session:
        session.exec(delete(ConsentRecord).where(ConsentRecord.resident_id == "resident_123"))
        session.commit()
    response = client.post(
        "/api/ai/generate-circles",
        headers=headers["operator"],
        json={"resident_ids": ["resident_123", "resident_234", "resident_345"]},
    )
    assert response.status_code == 403
