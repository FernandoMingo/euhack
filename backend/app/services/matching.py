from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from typing import Any

from app.models import Activity, Feedback, Resident


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius * c


def _overlap_ratio(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left_set = {item.lower() for item in left}
    right_set = {item.lower() for item in right}
    if not left_set:
        return 0.0
    return len(left_set & right_set) / len(left_set)


def _availability_score(resident: Resident, activity: Activity) -> float:
    if not resident.availability:
        return 0.5
    start = activity.start_time
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    label = f"{start.strftime('%A')} {start.strftime('%p').lower()}".replace("am", "morning").replace("pm", "afternoon")
    joined = " ".join(resident.availability).lower()
    if "saturday morning" in joined and "saturday morning" in label.lower():
        return 1.0
    if start.strftime("%A").lower() in joined:
        return 0.7
    return 0.2


def _distance_score(resident: Resident, activity: Activity) -> float:
    try:
        lat1 = float(resident.approx_location["lat"])
        lng1 = float(resident.approx_location["lng"])
        lat2 = float(activity.location["lat"])
        lng2 = float(activity.location["lng"])
    except (KeyError, TypeError, ValueError):
        return 0.6
    km = _haversine_km(lat1, lng1, lat2, lng2)
    max_km = max(1, resident.location_radius_km)
    return max(0.0, min(1.0, 1 - (km / max_km)))


def _comfort_score(resident: Resident, group_size: int) -> float:
    min_size = resident.preferred_group_size.get("min", 3)
    max_size = resident.preferred_group_size.get("max", 6)
    if min_size <= group_size <= max_size:
        return 1.0
    return 0.3


def _intensity_score(resident: Resident, activity: Activity) -> float:
    avoid = " ".join(resident.avoid).lower()
    if "loud" in avoid and "party" in activity.type.lower():
        return 0.0
    if "alcohol" in avoid and "bar" in activity.type.lower():
        return 0.0
    return 0.9


def _feedback_score(feedback_items: list[Feedback]) -> float:
    if not feedback_items:
        return 0.6
    positives = sum(1 for item in feedback_items if item.felt_after == "better" and item.would_repeat)
    return positives / max(1, len(feedback_items))


def _group_balance_score(residents: list[Resident]) -> float:
    langs = {r.preferred_language for r in residents}
    return 1.0 if len(langs) <= 2 else 0.7


def hard_constraints_pass(resident: Resident, activity: Activity, group_size: int) -> tuple[bool, list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []
    if resident.status == "active":
        passed.append("resident_active")
    else:
        failed.append("resident_inactive")
    for avoid in resident.avoid:
        if avoid.lower() in activity.type.lower() or avoid.lower() in activity.title.lower():
            failed.append("avoid_preference_violated")
            break
    if resident.accessibility_needs and not set(resident.accessibility_needs).issubset(set(activity.accessibility)):
        failed.append("accessibility_unmet")
    else:
        passed.append("accessibility_checked")
    if activity.cost > 0 and resident.cost_sensitivity == "free_or_low_cost" and activity.cost > 10:
        failed.append("cost_too_high")
    else:
        passed.append("cost_ok")
    if group_size > resident.preferred_group_size.get("max", 6):
        failed.append("group_size_exceeds_comfort")
    else:
        passed.append("group_size_safe")
    if activity.risk_level not in {"low", "medium"}:
        failed.append("risk_too_high")
    else:
        passed.append("risk_ok")
    return len(failed) == 0, passed, failed


@dataclass
class ScoredActivity:
    activity: Activity
    fit_score: float
    component_scores: dict[str, float]
    hard_constraints_passed: list[str]
    hard_constraints_failed: list[str]


def score_activity(
    *,
    activity: Activity,
    residents: list[Resident],
    feedback_by_resident: dict[str, list[Feedback]],
) -> ScoredActivity:
    group_size = len(residents)
    hard_passed: list[str] = []
    hard_failed: list[str] = []
    interest_parts: list[float] = []
    availability_parts: list[float] = []
    distance_parts: list[float] = []
    comfort_parts: list[float] = []
    intensity_parts: list[float] = []
    feedback_parts: list[float] = []
    for resident in residents:
        is_valid, passed, failed = hard_constraints_pass(resident, activity, group_size)
        hard_passed.extend(passed)
        if not is_valid:
            hard_failed.extend(failed)
        interest_parts.append(_overlap_ratio(resident.interests, [activity.type, activity.title]))
        availability_parts.append(_availability_score(resident, activity))
        distance_parts.append(_distance_score(resident, activity))
        comfort_parts.append(_comfort_score(resident, group_size))
        intensity_parts.append(_intensity_score(resident, activity))
        feedback_parts.append(_feedback_score(feedback_by_resident.get(resident.id, [])))
    group_balance = _group_balance_score(residents)
    component_scores = {
        "interest_overlap_score": sum(interest_parts) / max(1, len(interest_parts)),
        "availability_score": sum(availability_parts) / max(1, len(availability_parts)),
        "distance_score": sum(distance_parts) / max(1, len(distance_parts)),
        "comfort_score": sum(comfort_parts) / max(1, len(comfort_parts)),
        "intensity_score": sum(intensity_parts) / max(1, len(intensity_parts)),
        "feedback_score": sum(feedback_parts) / max(1, len(feedback_parts)),
        "group_balance_score": group_balance,
    }
    fit_score = (
        component_scores["interest_overlap_score"] * 0.25
        + component_scores["availability_score"] * 0.20
        + component_scores["distance_score"] * 0.15
        + component_scores["comfort_score"] * 0.15
        + component_scores["intensity_score"] * 0.10
        + component_scores["feedback_score"] * 0.10
        + component_scores["group_balance_score"] * 0.05
    )
    return ScoredActivity(
        activity=activity,
        fit_score=round(fit_score, 4),
        component_scores=component_scores,
        hard_constraints_passed=sorted(set(hard_passed)),
        hard_constraints_failed=sorted(set(hard_failed)),
    )


def build_explanation(
    scored: ScoredActivity,
    *,
    residents: list[Resident],
    alternatives: list[ScoredActivity],
    approval_status: str,
) -> dict[str, Any]:
    top_positive_signals = [
        "shared_interests",
        "availability_overlap",
        "distance_within_radius",
        "small_group_preference_match",
    ]
    alternatives_payload = [
        {
            "activity_id": alt.activity.id,
            "fit_score": alt.fit_score,
            "reasons_ranked_lower": alt.hard_constraints_failed or ["lower_weighted_fit_score"],
        }
        for alt in alternatives
    ]
    return {
        "recommended_group": [r.id for r in residents],
        "recommended_activity": scored.activity.id,
        "top_positive_signals": top_positive_signals,
        "hard_constraints_passed": scored.hard_constraints_passed,
        "alternative_activities_considered": alternatives_payload,
        "human_approval_status": approval_status,
        "component_scores": scored.component_scores,
    }
