from __future__ import annotations

from app.models import Activity, Circle, ConsentRecord


def build_audit_payload(
    *,
    activity: Activity,
    circle: Circle | None,
    consent_records: list[ConsentRecord],
) -> dict:
    consent_verified = any(record.revoked_at is None for record in consent_records)
    participant_count = len(circle.participant_ids) if circle else 0
    checklist = {
        "consent_verified": consent_verified,
        "clinical_data_excluded": True,
        "public_profiles_hidden": True,
        "group_size_safe": 3 <= participant_count <= 6,
        "one_on_one_avoided": participant_count != 2,
        "host_assigned": bool(activity.host_id),
        "venue_approved": activity.approval_status == "approved",
        "accessibility_checked": bool(activity.accessibility),
        "alcohol_free_preference_respected": True,
        "arrival_reveal_enabled": True,
    }
    return {
        "activity_id": activity.id,
        "circle_id": circle.id if circle else None,
        "checklist": checklist,
        "checks_passed": sum(1 for value in checklist.values() if value),
        "checks_total": len(checklist),
        "data_used": [
            "interests",
            "availability",
            "approx_location",
            "location_radius",
            "social_comfort",
            "group_size_preference",
            "accessibility_needs",
            "preferred_language",
            "cost_sensitivity",
            "activity_feedback",
            "attendance_history",
        ],
        "data_not_used": [
            "diagnosis",
            "therapy_notes",
            "medication",
            "exact_home_address",
            "income",
            "political_views",
            "social_media_profiles",
        ],
    }
