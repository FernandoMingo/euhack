"""Pure scoring functions for the matching engine.

No database access happens here; the engine wires the inputs in and the
outputs out. Cosine similarity ignores negative weights (avoidances) so the
result is always in ``[0, 1]``. The final score is a weighted combination of
cosine similarity plus soft signals (cost band alignment, availability
overlap) so two residents with identical interests but different cost
tolerances still produce distinguishable rankings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_W_COSINE = 0.70
_W_AVAILABILITY = 0.15
_W_COST = 0.15

_W_V2_COSINE = 0.55
_W_V2_AVAILABILITY = 0.10
_W_V2_COST = 0.10
_W_V2_COMFORT = 0.15
_W_V2_BEHAVIOR = 0.10


@dataclass(slots=True, frozen=True)
class ScoreBreakdown:
    cosine: float
    cost: float
    availability: float
    total: float
    comfort: float | None = None
    behavior: float | None = None


def _positive(features: dict[str, float]) -> dict[str, float]:
    return {k: v for k, v in features.items() if v > 0.0}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine over positive components of ``a`` and ``b``.

    Returns ``0.0`` if either vector has zero positive norm; the result is
    clamped to ``[0.0, 1.0]`` to absorb floating point drift.
    """
    pos_a = _positive(a)
    pos_b = _positive(b)
    if not pos_a or not pos_b:
        return 0.0
    smaller, larger = (pos_a, pos_b) if len(pos_a) <= len(pos_b) else (pos_b, pos_a)
    dot = 0.0
    for key, value in smaller.items():
        other = larger.get(key)
        if other is not None:
            dot += value * other
    norm_a = math.sqrt(sum(v * v for v in pos_a.values()))
    norm_b = math.sqrt(sum(v * v for v in pos_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    sim = dot / (norm_a * norm_b)
    if sim < 0.0:
        return 0.0
    if sim > 1.0:
        return 1.0
    return sim


def feature_contributions(
    resident: dict[str, float], activity: dict[str, float]
) -> dict[str, float]:
    """Per-feature positive contribution ``resident[k] * activity[k]``."""
    contribs: dict[str, float] = {}
    for key, resident_weight in resident.items():
        if resident_weight <= 0.0:
            continue
        activity_weight = activity.get(key, 0.0)
        if activity_weight <= 0.0:
            continue
        contribs[key] = resident_weight * activity_weight
    return contribs


def cost_compatibility_score(
    resident_allowed_bands: list[str],
    template_cost_band: str,
) -> float:
    """1.0 when the template's cost band is allowed by the resident, else 0.0."""
    if not resident_allowed_bands:
        return 1.0
    return 1.0 if template_cost_band in resident_allowed_bands else 0.0


def availability_overlap_score(resident_availability_buckets: set[str]) -> float:
    """Activity templates are time-agnostic, so this is a presence signal.

    Residents who provided availability score 1.0 (engine has the data it
    needs to later align concrete activities); residents with no availability
    rows score 0.5 because we have less information for them.
    """
    return 1.0 if resident_availability_buckets else 0.5


def weighted_total(
    *,
    cosine: float,
    cost_score: float,
    availability_score: float,
) -> ScoreBreakdown:
    """Combine cosine + soft signals into a final score in ``[0, 1]``."""
    total = (
        _W_COSINE * cosine
        + _W_AVAILABILITY * availability_score
        + _W_COST * cost_score
    )
    if total < 0.0:
        total = 0.0
    if total > 1.0:
        total = 1.0
    return ScoreBreakdown(
        cosine=cosine,
        cost=cost_score,
        availability=availability_score,
        total=total,
    )


def behavior_score_from_adjustment(adjustment: float) -> float:
    """Map a bounded ``[-1, 1]`` behavior adjustment into ``[0, 1]``."""
    score = 0.5 + adjustment / 2.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def weighted_total_v2(
    *,
    cosine: float,
    cost_score: float,
    availability_score: float,
    comfort_score: float,
    behavior_score: float,
) -> ScoreBreakdown:
    """Combine v2 activity-fit, practicality, comfort, and behavior signals."""
    total = (
        _W_V2_COSINE * cosine
        + _W_V2_AVAILABILITY * availability_score
        + _W_V2_COST * cost_score
        + _W_V2_COMFORT * comfort_score
        + _W_V2_BEHAVIOR * behavior_score
    )
    if total < 0.0:
        total = 0.0
    if total > 1.0:
        total = 1.0
    return ScoreBreakdown(
        cosine=cosine,
        cost=cost_score,
        availability=availability_score,
        comfort=comfort_score,
        behavior=behavior_score,
        total=total,
    )
