from __future__ import annotations

from datetime import datetime

from app.models import Activity, Feedback, Resident
from app.services.matching import build_explanation, hard_constraints_pass, score_activity


def _resident(resident_id: str = "resident_test", **overrides) -> Resident:
    payload = {
        "id": resident_id,
        "first_name": "Sofia",
        "email": f"{resident_id}@example.com",
        "preferred_language": "English",
        "approx_location": {"lat": 52.3602, "lng": 4.8645},
        "location_radius_km": 3,
        "interests": ["photography", "parks"],
        "activity_preferences": ["walks"],
        "availability": ["Saturday morning"],
        "social_comfort": "small_group_low_pressure",
        "preferred_group_size": {"min": 3, "max": 6},
        "accessibility_needs": ["step_free_route"],
        "cost_sensitivity": "free_or_low_cost",
        "avoid": ["alcohol"],
        "profile_visibility": {"first_name": True},
        "status": "active",
    }
    payload.update(overrides)
    return Resident(**payload)


def _activity(activity_id: str = "activity_test", **overrides) -> Activity:
    payload = {
        "id": activity_id,
        "title": "Calm Photography Walk",
        "type": "photography_walk",
        "location": {"lat": 52.3579, "lng": 4.8686},
        "start_time": datetime.fromisoformat("2026-05-23T10:30:00+02:00"),
        "end_time": datetime.fromisoformat("2026-05-23T12:00:00+02:00"),
        "capacity": 6,
        "host_id": "host_001",
        "cost": 0,
        "accessibility": ["step_free_route"],
        "risk_level": "low",
        "approval_status": "approved",
        "lifecycle_status": "approved",
    }
    payload.update(overrides)
    return Activity(**payload)


def test_hard_constraints_pass_for_healthy_match():
    resident = _resident()
    activity = _activity()
    ok, passed, failed = hard_constraints_pass(resident, activity, group_size=5)
    assert ok is True
    assert "risk_ok" in passed
    assert failed == []


def test_hard_constraints_fail_on_accessibility_and_risk():
    resident = _resident(accessibility_needs=["step_free_route", "wheelchair_access"])
    activity = _activity(accessibility=["step_free_route"], risk_level="high")
    ok, passed, failed = hard_constraints_pass(resident, activity, group_size=5)
    assert ok is False
    assert "accessibility_unmet" in failed
    assert "risk_too_high" in failed
    assert "cost_ok" in passed


def test_score_activity_is_deterministic_and_contains_component_scores():
    resident_a = _resident("resident_a")
    resident_b = _resident("resident_b", preferred_language="Dutch")
    activity = _activity()
    feedback = {
        "resident_a": [Feedback(id="fb1", resident_id="resident_a", activity_id="a1", attended=True, felt_after="better", activity_fit="yes", group_comfort="yes", would_repeat=True)],
        "resident_b": [],
    }
    first = score_activity(activity=activity, residents=[resident_a, resident_b], feedback_by_resident=feedback)
    second = score_activity(activity=activity, residents=[resident_a, resident_b], feedback_by_resident=feedback)
    assert first.fit_score == second.fit_score
    assert set(first.component_scores.keys()) == {
        "interest_overlap_score",
        "availability_score",
        "distance_score",
        "comfort_score",
        "intensity_score",
        "feedback_score",
        "group_balance_score",
    }


def test_build_explanation_includes_required_fields():
    residents = [_resident("resident_1"), _resident("resident_2")]
    primary = score_activity(activity=_activity("activity_001"), residents=residents, feedback_by_resident={})
    alt = score_activity(activity=_activity("activity_002", type="museum_visit", title="Museum Morning"), residents=residents, feedback_by_resident={})
    explanation = build_explanation(
        primary,
        residents=residents,
        alternatives=[alt],
        approval_status="pending_approval",
    )
    assert explanation["recommended_activity"] == "activity_001"
    assert explanation["human_approval_status"] == "pending_approval"
    assert len(explanation["top_positive_signals"]) >= 3
    assert explanation["alternative_activities_considered"][0]["activity_id"] == "activity_002"
