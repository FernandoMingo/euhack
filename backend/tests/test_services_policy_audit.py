from __future__ import annotations

from datetime import datetime

from app.models import Activity, Circle, ConsentRecord
from app.services.audit import build_audit_payload
from app.services.policy import has_active_matching_consent, project_resident_for_matching, sanitize_preferences_update


def test_has_active_matching_consent_true_when_scope_present():
    consents = [
        ConsentRecord(
            id="c1",
            resident_id="r1",
            professional_id="p1",
            consent_scope=["create_social_profile", "use_profile_for_activity_matching"],
            revoked_at=None,
        )
    ]
    assert has_active_matching_consent(consents) is True


def test_has_active_matching_consent_false_when_revoked_or_missing_scope():
    consents = [
        ConsentRecord(
            id="c1",
            resident_id="r1",
            professional_id="p1",
            consent_scope=["create_social_profile"],
            revoked_at=datetime.now(),
        )
    ]
    assert has_active_matching_consent(consents) is False


def test_sanitize_preferences_removes_denied_fields():
    prefs = {
        "group_size_max": 5,
        "diagnosis": "not_allowed",
        "income": "not_allowed",
        "activity_intensity": "low",
    }
    safe = sanitize_preferences_update(prefs)
    assert "diagnosis" not in safe
    assert "income" not in safe
    assert safe["group_size_max"] == 5


def test_project_resident_for_matching_returns_allowlist_only():
    resident_dict = {
        "interests": ["photography"],
        "availability": ["Saturday morning"],
        "diagnosis": "should_be_removed",
        "medical_history": "should_be_removed",
        "custom_field": "not_allowlisted",
    }
    projected = project_resident_for_matching(resident_dict)
    assert "diagnosis" not in projected
    assert "medical_history" not in projected
    assert "custom_field" not in projected
    assert projected["interests"] == ["photography"]


def test_build_audit_payload_includes_expected_checklist_and_data_policy():
    activity = Activity(
        id="activity_001",
        title="Calm Photography Walk",
        type="photography_walk",
        location={"lat": 52.3, "lng": 4.8},
        start_time=datetime.fromisoformat("2026-05-23T10:30:00+02:00"),
        end_time=datetime.fromisoformat("2026-05-23T12:00:00+02:00"),
        capacity=6,
        host_id="host_001",
        cost=0,
        accessibility=["step_free_route"],
        risk_level="low",
        approval_status="approved",
    )
    circle = Circle(
        id="circle_001",
        activity_id="activity_001",
        participant_ids=["resident_1", "resident_2", "resident_3"],
        shared_signals=["parks"],
        fit_score=0.88,
    )
    payload = build_audit_payload(
        activity=activity,
        circle=circle,
        consent_records=[
            ConsentRecord(
                id="consent_1",
                resident_id="resident_1",
                professional_id="professional_1",
                consent_scope=["use_profile_for_activity_matching"],
            )
        ],
    )
    assert payload["checks_total"] >= 10
    assert payload["checklist"]["consent_verified"] is True
    assert "diagnosis" in payload["data_not_used"]
    assert "interests" in payload["data_used"]
