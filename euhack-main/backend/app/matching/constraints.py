"""Hard constraint checks for the matching engine.

A template that fails any check is rejected before scoring, so we never
recommend something that violates an avoidance, exceeds cost tolerance,
forces an unwanted group size, or oversells the resident's social comfort.
Each rejection is recorded with a stable reason string for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dataclasses import (
    ActivityTemplate,
    Resident,
    ResidentAvoidance,
)
from app.matching.vectorizer import (
    _normalize,
    allowed_cost_bands,
    social_energy_from_comfort,
)


@dataclass(slots=True, frozen=True)
class ConstraintResult:
    passed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _template_signals(template: ActivityTemplate, template_tags: list[str]) -> set[str]:
    signals = {_normalize(template.family), _normalize(template.code), _normalize(template.title)}
    for tag in template_tags:
        if ":" not in tag:
            signals.add(_normalize(tag))
            continue
        kind, _, raw_value = tag.partition(":")
        if raw_value:
            signals.add(_normalize(raw_value))
            signals.add(f"{_normalize(kind)}:{_normalize(raw_value)}")
    return {s for s in signals if s}


def check_template_constraints(
    *,
    resident: Resident,
    avoidances: list[ResidentAvoidance],
    template: ActivityTemplate,
    template_tags: list[str],
    accessibility_needs: list[str],
) -> ConstraintResult:
    """Return whether ``template`` passes all v1 hard constraints for ``resident``."""
    reasons: list[str] = []

    template_signals = _template_signals(template, template_tags)
    for avoidance in sorted(avoidances, key=lambda a: a.value):
        avoid_value = _normalize(avoidance.value)
        if not avoid_value:
            continue
        if avoid_value in template_signals:
            reasons.append(f"avoidance:{avoid_value}")

    bands = allowed_cost_bands(resident.cost_sensitivity)
    if template.typical_cost_band not in bands:
        reasons.append(f"cost_band_excluded:{template.typical_cost_band}")

    if template.typical_group_size_max < resident.preferred_group_size_min:
        reasons.append("group_size_too_small")
    if template.typical_group_size_min > resident.preferred_group_size_max:
        reasons.append("group_size_too_large")

    resident_energy = social_energy_from_comfort(resident.social_comfort)
    if resident_energy == "low" and template.social_energy == "high":
        reasons.append("social_energy_too_high")

    if accessibility_needs and template.intensity == "vigorous":
        reasons.append("accessibility_intensity_too_high")
    if accessibility_needs and template.risk_level == "high":
        reasons.append("accessibility_risk_too_high")

    return ConstraintResult(passed=not reasons, reasons=tuple(reasons))
