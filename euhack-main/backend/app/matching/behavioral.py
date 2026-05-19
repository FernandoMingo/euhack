"""Safe behavioral signals for matching v2.

This module converts existing product interaction rows into bounded,
decayed matching signals. It intentionally avoids clinical data and raw peer
ratings; only attendance, invitation decisions, resident feedback, and safety
flags are considered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlite3 import Row

from app.matching.vectorizer import _normalize

BEHAVIORAL_MODEL_VERSION = "v2"
BEHAVIOR_DECAY_BASE = 0.95
MAX_BEHAVIOR_FEATURE_BOOST = 0.30
MAX_TEMPLATE_ADJUSTMENT = 0.25
MAX_FAMILY_ADJUSTMENT = 0.18


@dataclass(slots=True, frozen=True)
class BehavioralProfile:
    """Bounded behavior-derived signals for one resident."""

    feature_weights: dict[str, float] = field(default_factory=dict)
    template_adjustments: dict[str, float] = field(default_factory=dict)
    family_adjustments: dict[str, float] = field(default_factory=dict)
    positive_events: int = 0
    negative_events: int = 0
    safety_events: int = 0

    def adjustment_for(self, *, template_code: str, family: str) -> float:
        template_key = _normalize(template_code)
        family_key = _normalize(family)
        total = self.template_adjustments.get(template_key, 0.0)
        total += self.family_adjustments.get(family_key, 0.0)
        if total < -1.0:
            return -1.0
        if total > 1.0:
            return 1.0
        return total


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


def _weeks_old(event_at: datetime | None, now: datetime) -> float:
    if event_at is None:
        return 0.0
    if event_at.tzinfo is None:
        event_at = event_at.replace(tzinfo=timezone.utc)
    delta = now - event_at
    if delta.total_seconds() <= 0:
        return 0.0
    return delta.days / 7.0


def _decay(event_at: datetime | None, now: datetime) -> float:
    return BEHAVIOR_DECAY_BASE ** _weeks_old(event_at, now)


def _clamp(value: float, limit: float) -> float:
    if value > limit:
        return limit
    if value < -limit:
        return -limit
    return value


def _add(mapping: dict[str, float], key: str, value: float, limit: float) -> None:
    mapping[key] = _clamp(mapping.get(key, 0.0) + value, limit)


def _row_event_time(row: Row) -> datetime | None:
    for key in (
        "feedback_created_at",
        "safety_created_at",
        "check_out_at",
        "check_in_at",
        "invitation_responded_at",
        "invitation_sent_at",
        "activity_start_at",
    ):
        value = _parse_dt(row[key])
        if value is not None:
            return value
    return None


def build_behavioral_profile(
    rows: list[Row],
    *,
    now: datetime | None = None,
) -> BehavioralProfile:
    """Build bounded, decayed behavioral signals from repository rows."""
    now = now or datetime.now(timezone.utc)
    feature_weights: dict[str, float] = {}
    template_adjustments: dict[str, float] = {}
    family_adjustments: dict[str, float] = {}
    positive_events = 0
    negative_events = 0
    safety_events = 0

    for row in rows:
        template_code = _normalize(row["template_code"] or "")
        family = _normalize(row["family"] or "")
        if not template_code:
            continue
        event_at = _row_event_time(row)
        decay = _decay(event_at, now)
        signal = 0.0

        invitation_status = row["invitation_status"]
        if invitation_status == "accepted":
            signal += 0.06
            positive_events += 1
        elif invitation_status == "declined":
            signal -= 0.10
            negative_events += 1
        elif invitation_status == "expired":
            signal -= 0.05
            negative_events += 1

        attendance_status = row["attendance_status"]
        if attendance_status == "attended":
            signal += 0.14
            positive_events += 1
        elif attendance_status == "no_show":
            signal -= 0.10
            negative_events += 1

        if row["activity_fit"] == 1:
            signal += 0.15
            positive_events += 1
        elif row["activity_fit"] == 0:
            signal -= 0.14
            negative_events += 1

        if row["would_repeat"] == 1:
            signal += 0.15
            positive_events += 1
        elif row["would_repeat"] == 0:
            signal -= 0.14
            negative_events += 1

        if row["group_comfort"] == 1:
            signal += 0.08
            positive_events += 1
        elif row["group_comfort"] == 0:
            signal -= 0.08
            negative_events += 1

        felt_after = row["felt_after"]
        if felt_after == "better":
            signal += 0.05
            positive_events += 1
        elif felt_after == "worse":
            signal -= 0.08
            negative_events += 1

        if row["feedback_safety_reported"] == 1:
            signal -= 0.30
            safety_events += 1
        if row["safety_escalation_level"] in {"operator_review", "urgent"}:
            signal -= 0.35
            safety_events += 1

        decayed_signal = signal * decay
        if decayed_signal == 0.0:
            continue

        _add(
            template_adjustments,
            template_code,
            decayed_signal,
            MAX_TEMPLATE_ADJUSTMENT,
        )
        if family:
            _add(
                family_adjustments,
                family,
                decayed_signal * 0.6,
                MAX_FAMILY_ADJUSTMENT,
            )
        if decayed_signal > 0.0:
            _add(
                feature_weights,
                f"activity_pref:{template_code}",
                decayed_signal,
                MAX_BEHAVIOR_FEATURE_BOOST,
            )
            if family:
                _add(
                    feature_weights,
                    f"family:{family}",
                    decayed_signal * 0.6,
                    MAX_BEHAVIOR_FEATURE_BOOST,
                )

    return BehavioralProfile(
        feature_weights=dict(sorted(feature_weights.items())),
        template_adjustments=dict(sorted(template_adjustments.items())),
        family_adjustments=dict(sorted(family_adjustments.items())),
        positive_events=positive_events,
        negative_events=negative_events,
        safety_events=safety_events,
    )
