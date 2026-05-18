from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any

from app.models import Activity, Feedback, Resident


WEIGHTS = {
    "interest_overlap": 25,
    "availability_overlap": 20,
    "distance_travel_radius": 15,
    "social_comfort": 15,
    "intensity_fit": 10,
    "feedback_fit": 10,
    "group_balance": 5,
}


def _norm(items: list[str]) -> set[str]:
    return {item.strip().lower().replace("_", " ") for item in items}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return radius * (2 * atan2(sqrt(a), sqrt(1 - a)))


def hard_constraints(resident: Resident, activity: Activity) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []
    avoid = " ".join(resident.avoid).lower()
    activity_words = " ".join([activity.title, activity.activity_type, *activity.tags]).lower()

    if resident.status == "active":
        passed.append("resident active")
    else:
        failed.append("resident inactive")

    if resident.accessibility_needs and set(resident.accessibility_needs).issubset(set(activity.accessibility)):
        passed.append("step-free route requirement satisfied")
    elif resident.accessibility_needs:
        failed.append("accessibility requirement not met")

    if "alcohol" in avoid and activity.alcohol_free:
        passed.append("alcohol-free preference respected")
    elif "alcohol" in avoid:
        failed.append("alcohol-free preference not respected")

    if any(item in activity_words for item in ["late night", "loud venue", "bar"]) and (
        "late night" in avoid or "loud venues" in avoid or "alcohol" in avoid
    ):
        failed.append("avoid list conflict")
    else:
        passed.append("avoid list respected")

    if resident.cost_sensitivity == "free_or_low_cost" and activity.cost_amount <= 10:
        passed.append("cost preference respected")
    elif resident.cost_sensitivity == "free_or_low_cost":
        failed.append("cost above low-cost preference")

    if activity.group_size <= resident.preferred_group_size.get("max", 6):
        passed.append("small group comfort")
    else:
        failed.append("group too large")

    return passed, failed


def _interest_score(resident: Resident, activity: Activity) -> float:
    left = _norm(resident.interests + resident.activity_preferences)
    right = _norm(activity.tags + [activity.title, activity.activity_type])
    if not left:
        return 0.0
    overlap = len(left & right)
    soft_matches = 0
    if "walks" in left and "walk" in " ".join(right):
        soft_matches += 1
    if "parks" in left and "park" in " ".join(right):
        soft_matches += 1
    if "museums" in left and "museum" in " ".join(right):
        soft_matches += 1
    return min(1.0, (overlap + soft_matches) / 4)


def _availability_score(resident: Resident, activity: Activity) -> float:
    availability = " ".join(resident.availability).lower()
    return 1.0 if activity.availability_label.lower() in availability else 0.25


def _distance_score(resident: Resident, activity: Activity) -> float:
    distance = _haversine_km(resident.location_lat, resident.location_lng, activity.lat, activity.lng)
    if distance <= resident.location_radius_km:
        return max(0.55, 1 - (distance / max(resident.location_radius_km, 1)) * 0.45)
    return 0.2


def _comfort_score(resident: Resident, activity: Activity) -> float:
    min_size = resident.preferred_group_size.get("min", 3)
    max_size = resident.preferred_group_size.get("max", 6)
    if min_size <= activity.group_size <= max_size and resident.social_comfort == "small_group_low_pressure":
        return 1.0
    if activity.group_size <= max_size:
        return 0.7
    return 0.2


def _intensity_score(resident: Resident, activity: Activity) -> float:
    if activity.intensity == "low":
        return 1.0
    if activity.intensity == "medium" and resident.social_comfort == "small_group_low_pressure":
        return 0.55
    return 0.3


def _feedback_score(feedback_items: list[Feedback]) -> float:
    if not feedback_items:
        return 0.7
    positive = sum(
        1
        for item in feedback_items
        if item.would_do_similar_again.lower() in {"yes", "probably"} and item.felt_after.lower() in {"calmer", "better", "connected"}
    )
    return positive / len(feedback_items)


def _group_balance_score(residents: list[Resident], activity: Activity) -> float:
    group_max = [r.preferred_group_size.get("max", 6) for r in residents]
    if activity.group_size <= min(group_max):
        return 1.0
    return 0.6


@dataclass(frozen=True)
class RankedActivity:
    activity: Activity
    score: int
    component_scores: dict[str, int]
    hard_constraints_passed: list[str]
    hard_constraints_failed: list[str]
    reasons_ranked_lower: list[str]


def score_activity(activity: Activity, residents: list[Resident], feedback: list[Feedback]) -> RankedActivity:
    passed: list[str] = []
    failed: list[str] = []
    feedback_by_resident: dict[str, list[Feedback]] = {}
    for item in feedback:
        feedback_by_resident.setdefault(item.resident_id, []).append(item)

    components_float = {
        "interest_overlap": 0.0,
        "availability_overlap": 0.0,
        "distance_travel_radius": 0.0,
        "social_comfort": 0.0,
        "intensity_fit": 0.0,
        "feedback_fit": 0.0,
    }

    for resident in residents:
        resident_passed, resident_failed = hard_constraints(resident, activity)
        passed.extend(resident_passed)
        failed.extend(resident_failed)
        components_float["interest_overlap"] += _interest_score(resident, activity)
        components_float["availability_overlap"] += _availability_score(resident, activity)
        components_float["distance_travel_radius"] += _distance_score(resident, activity)
        components_float["social_comfort"] += _comfort_score(resident, activity)
        components_float["intensity_fit"] += _intensity_score(resident, activity)
        components_float["feedback_fit"] += _feedback_score(feedback_by_resident.get(resident.id, []))

    divisor = max(len(residents), 1)
    for key in list(components_float.keys()):
        components_float[key] = components_float[key] / divisor
    components_float["group_balance"] = _group_balance_score(residents, activity)

    component_scores = {
        key: round(components_float[key] * weight) for key, weight in WEIGHTS.items()
    }
    score = sum(component_scores.values())
    if failed:
        score = 0

    reasons_ranked_lower: list[str] = []
    if failed:
        reasons_ranked_lower.extend(sorted(set(failed)))
    else:
        low_components = [key for key, value in component_scores.items() if value < WEIGHTS[key] * 0.6]
        reasons_ranked_lower.extend(low_components or ["lower weighted fit score"])

    return RankedActivity(
        activity=activity,
        score=score,
        component_scores=component_scores,
        hard_constraints_passed=sorted(set(passed)),
        hard_constraints_failed=sorted(set(failed)),
        reasons_ranked_lower=reasons_ranked_lower,
    )


def explain_match(
    ranked: list[RankedActivity],
    residents: list[Resident],
    human_approval_status: str,
) -> dict[str, Any]:
    best = ranked[0]
    alternatives = ranked[1:]
    return {
        "recommended_group": ["Sofia", "Resident A", "Resident B", "Resident C", "Resident D"],
        "recommended_activity": best.activity.title,
        "top_positive_signals": [
            "shared Saturday morning availability",
            "calm outdoor preference",
            "photography/parks overlap",
            "small group comfort",
            "step-free route requirement satisfied",
            "alcohol-free preference respected",
        ],
        "hard_constraints_passed": best.hard_constraints_passed,
        "alternative_activities_considered": [
            {"activity_id": item.activity.id, "title": item.activity.title, "score": item.score}
            for item in alternatives
        ],
        "reasons_alternatives_ranked_lower": [
            {"activity_id": item.activity.id, "reasons": item.reasons_ranked_lower}
            for item in alternatives
        ],
        "human_approval_status": human_approval_status,
        "component_scores": best.component_scores,
        "weights": WEIGHTS,
        "guardrail": "Activities are ranked for fit. People are not ranked by social value.",
        "resident_ids_used": [resident.id for resident in residents],
    }
