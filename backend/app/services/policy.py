from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.models import ConsentRecord

REQUIRED_MATCHING_SCOPE = "use_profile_for_activity_matching"

ALLOWED_MATCH_FIELDS = {
    "interests",
    "activity_preferences",
    "availability",
    "approx_location",
    "location_radius_km",
    "social_comfort",
    "preferred_group_size",
    "accessibility_needs",
    "preferred_language",
    "cost_sensitivity",
    "avoid",
    "preferences_extra",
}

DENIED_FIELDS = {
    "diagnosis",
    "therapy_notes",
    "medication",
    "medical_history",
    "exact_home_address",
    "income",
    "political_views",
    "social_media",
}


def has_active_matching_consent(consents: Iterable[ConsentRecord]) -> bool:
    for consent in consents:
        if consent.revoked_at is None and REQUIRED_MATCHING_SCOPE in consent.consent_scope:
            return True
    return False


def sanitize_preferences_update(prefs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in prefs.items() if k not in DENIED_FIELDS}


def project_resident_for_matching(resident_dict: dict[str, Any]) -> dict[str, Any]:
    for denied in DENIED_FIELDS:
        resident_dict.pop(denied, None)
    return {k: v for k, v in resident_dict.items() if k in ALLOWED_MATCH_FIELDS}
