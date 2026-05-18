"""Explanation builders for matching candidates.

Each candidate gets:

* a short ``summary_text`` operators can scan in a list view
* a structured ``payload`` (JSON-serialisable) capturing the score breakdown,
  the top positive features, constraint outcomes, and the model version

The payload is intentionally deterministic: feature lists are sorted by
contribution then key, numeric fields are rounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.matching.scoring import ScoreBreakdown

_TOP_FEATURE_COUNT = 5


@dataclass(slots=True, frozen=True)
class Explanation:
    summary_text: str
    payload: dict[str, Any]


def _humanize_feature(key: str, contribution: float) -> str:
    kind, _, value = key.partition(":")
    pretty_value = value.replace("_", " ") if value else key
    if not value:
        return f"{kind} (+{contribution:.2f})"
    return f"{kind} match on {pretty_value} (+{contribution:.2f})"


def _top_features(contributions: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(contributions.items(), key=lambda kv: (-kv[1], kv[0]))[:_TOP_FEATURE_COUNT]


def build_explanation(
    *,
    template_title: str,
    template_code: str,
    rank_position: int,
    model_version: str,
    breakdown: ScoreBreakdown,
    contributions: dict[str, float],
    constraint_passed: bool,
    constraint_reasons: tuple[str, ...] | list[str] = (),
) -> Explanation:
    """Construct the summary string and structured payload for one candidate."""
    reasons = tuple(constraint_reasons)
    top = _top_features(contributions)

    if constraint_passed:
        if top:
            highlights = ", ".join(
                key.split(":", 1)[1].replace("_", " ") if ":" in key else key
                for key, _ in top[:3]
            )
            summary = (
                f"#{rank_position} {template_title}: cosine {breakdown.cosine:.2f}, "
                f"total {breakdown.total:.2f}. Strong overlap on {highlights}."
            )
        else:
            summary = (
                f"#{rank_position} {template_title}: weak overlap "
                f"(total {breakdown.total:.2f})."
            )
    else:
        reason_text = "; ".join(reasons) if reasons else "constraint failed"
        summary = f"#{rank_position} {template_title}: filtered out ({reason_text})."

    payload: dict[str, Any] = {
        "model_version": model_version,
        "template_code": template_code,
        "rank_position": rank_position,
        "score_breakdown": {
            "cosine": round(breakdown.cosine, 6),
            "cost_alignment": round(breakdown.cost, 6),
            "availability_overlap": round(breakdown.availability, 6),
            "total": round(breakdown.total, 6),
        },
        "top_features": [
            {
                "feature_key": key,
                "contribution": round(value, 6),
                "humanized": _humanize_feature(key, value),
            }
            for key, value in top
        ],
        "constraints": {
            "passed": constraint_passed,
            "reasons": list(reasons),
        },
    }
    return Explanation(summary_text=summary, payload=payload)
