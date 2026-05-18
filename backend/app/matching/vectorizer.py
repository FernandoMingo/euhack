"""Resident and activity template vectorization.

Pure functions that turn structured profile/template state into a sparse
feature dictionary, plus thin persistence helpers that write the resulting
weights through ``MatchingRepository`` for explainability.

Feature key namespace (mirrors AGENTS.md section 10):

* ``interest:<value>`` – topical interest signal (1.0 explicit, 0.6/0.7 derived)
* ``activity_pref:<code>`` – preferred activity / template code
* ``avoid:<value>`` – negative-weight avoidance signal (AVOIDANCE_WEIGHT)
* ``access:<value>`` – accessibility need / capability
* ``avail:<weekday>_<bucket>`` – resident-only availability slot
* ``social_energy:<low|medium|high>`` – social comfort level
* ``group_size:<n>`` – preferred / typical group size buckets
* ``cost:<band>`` – cost band (free|low|medium|high)
* ``setting:<value>`` / ``intensity:<value>`` / ``noise:<value>`` /
  ``structure:<value>`` / ``risk:<value>`` / ``family:<value>`` –
  activity-side structured attributes
* ``theme:<value>`` / ``attribute:<value>`` / ``skill:<value>`` /
  ``format:<value>`` – mirrored from activity template tags

Avoidance weights are stored as negative numbers for full auditability.
The scoring layer ignores negative weights when computing cosine similarity
so the cosine score is always in ``[0, 1]``; avoidances act primarily as
hard constraints in :mod:`app.matching.constraints`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from app.dataclasses import (
    ActivityTemplate,
    Resident,
    ResidentAvailability,
    ResidentAvoidance,
    ResidentPreference,
)
from app.repositories.matching_repository import MatchingRepository

DEFAULT_MODEL_VERSION = "v1"

AVOIDANCE_WEIGHT = -1.5

logger = logging.getLogger(__name__)

_TIME_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("morning", 6, 12),
    ("afternoon", 12, 17),
    ("evening", 17, 23),
)

_TOKEN_BLOCKLIST = {"and", "the", "for", "with", "from", "your", "you"}


@dataclass(slots=True, frozen=True)
class FeatureVector:
    """Sparse feature vector produced by the vectorizer.

    ``features`` is a deterministic mapping from feature key to weight.
    """

    owner_id: str
    owner_kind: str
    features: dict[str, float] = field(default_factory=dict)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _tokens_from_phrase(phrase: str) -> list[str]:
    return [
        tok
        for tok in _normalize(phrase).split("_")
        if len(tok) >= 4 and tok not in _TOKEN_BLOCKLIST
    ]


def _set_max(features: dict[str, float], key: str, weight: float) -> None:
    current = features.get(key)
    if current is None or weight > current:
        features[key] = weight


def _parse_hour(value: str) -> int:
    parts = value.split(":")
    if not parts or not parts[0].isdigit():
        return 0
    return max(0, min(23, int(parts[0])))


def availability_buckets_for_window(start_local: str, end_local: str) -> list[str]:
    """Return ordered bucket labels overlapping the window (morning/afternoon/evening)."""
    start_hour = _parse_hour(start_local)
    end_hour = _parse_hour(end_local)
    if end_hour <= start_hour:
        end_hour = start_hour + 1
    hits: list[str] = []
    for label, bstart, bend in _TIME_BUCKETS:
        if start_hour < bend and end_hour > bstart:
            hits.append(label)
    return hits


def social_energy_from_comfort(social_comfort: str) -> str:
    sc = social_comfort.lower()
    if "high" in sc:
        return "high"
    if "low" in sc:
        return "low"
    if "moderate" in sc or "medium" in sc:
        return "medium"
    return "medium"


def allowed_cost_bands(cost_sensitivity: str) -> list[str]:
    cs = cost_sensitivity.lower()
    if "free_only" in cs:
        return ["free"]
    if "free_or_low" in cs or "low_cost" in cs:
        return ["free", "low"]
    if "moderate" in cs:
        return ["free", "low", "medium"]
    if "any" in cs:
        return ["free", "low", "medium", "high"]
    return ["free", "low"]


def build_resident_vector(
    resident: Resident,
    preferences: Iterable[ResidentPreference],
    availabilities: Iterable[ResidentAvailability],
    avoidances: Iterable[ResidentAvoidance],
    behavioral_features: dict[str, float] | None = None,
) -> FeatureVector:
    """Build a sparse feature dict for a resident from their structured state."""
    preferences = list(preferences)
    availabilities = list(availabilities)
    avoidances = list(avoidances)
    feats: dict[str, float] = {}

    for pref in preferences:
        value = _normalize(pref.value)
        if not value:
            continue
        if pref.preference_type == "interest":
            _set_max(feats, f"interest:{value}", 1.0)
        elif pref.preference_type == "activity":
            _set_max(feats, f"activity_pref:{value}", 1.0)
            for tok in _tokens_from_phrase(pref.value):
                _set_max(feats, f"interest:{tok}", 0.6)
        elif pref.preference_type == "accessibility_need":
            _set_max(feats, f"access:{value}", 1.0)

    for avoid in avoidances:
        value = _normalize(avoid.value)
        if not value:
            continue
        feats[f"avoid:{value}"] = AVOIDANCE_WEIGHT

    for avail in availabilities:
        for bucket in availability_buckets_for_window(
            avail.start_time_local, avail.end_time_local
        ):
            _set_max(feats, f"avail:{avail.weekday}_{bucket}", 1.0)

    _set_max(feats, f"social_energy:{social_energy_from_comfort(resident.social_comfort)}", 1.0)

    for n in range(resident.preferred_group_size_min, resident.preferred_group_size_max + 1):
        _set_max(feats, f"group_size:{n}", 1.0)

    for band in allowed_cost_bands(resident.cost_sensitivity):
        _set_max(feats, f"cost:{band}", 1.0)

    for key, weight in (behavioral_features or {}).items():
        if weight > 0.0:
            feats[key] = feats.get(key, 0.0) + weight

    logger.debug(
        "vectorizer.resident resident=%s features=%d prefs=%d avails=%d avoids=%d",
        resident.id,
        len(feats),
        len(preferences),
        len(availabilities),
        len(avoidances),
    )
    return FeatureVector(
        owner_id=resident.id,
        owner_kind="resident",
        features=dict(sorted(feats.items())),
    )


def build_template_vector(
    template: ActivityTemplate, tags: Iterable[str]
) -> FeatureVector:
    """Build a sparse feature dict for an activity template plus its tags."""
    tags = list(tags)
    feats: dict[str, float] = {}

    _set_max(feats, f"family:{_normalize(template.family)}", 1.0)
    _set_max(feats, f"activity_pref:{_normalize(template.code)}", 1.0)
    _set_max(feats, f"social_energy:{template.social_energy}", 1.0)
    _set_max(feats, f"setting:{template.setting}", 1.0)
    _set_max(feats, f"intensity:{template.intensity}", 1.0)
    _set_max(feats, f"noise:{template.noise_level}", 1.0)
    _set_max(feats, f"structure:{template.structure}", 0.5)
    _set_max(feats, f"cost:{template.typical_cost_band}", 1.0)
    _set_max(feats, f"risk:{template.risk_level}", 0.5)

    for n in range(template.typical_group_size_min, template.typical_group_size_max + 1):
        _set_max(feats, f"group_size:{n}", 1.0)

    for tag in tags:
        if not tag or ":" not in tag:
            continue
        kind, _, raw_value = tag.partition(":")
        value = _normalize(raw_value)
        if not value:
            continue
        if kind == "theme":
            _set_max(feats, f"theme:{value}", 1.0)
            _set_max(feats, f"interest:{value}", 1.0)
        elif kind == "attribute":
            _set_max(feats, f"attribute:{value}", 1.0)
            _set_max(feats, f"interest:{value}", 0.7)
        elif kind == "access":
            _set_max(feats, f"access:{value}", 1.0)
        elif kind == "skill":
            _set_max(feats, f"skill:{value}", 0.5)
        elif kind == "format":
            _set_max(feats, f"format:{value}", 0.5)
        else:
            _set_max(feats, f"{_normalize(kind)}:{value}", 0.5)

    for tok in _tokens_from_phrase(template.code) + _tokens_from_phrase(template.title):
        _set_max(feats, f"interest:{tok}", 0.6)

    logger.debug(
        "vectorizer.template template=%s features=%d tags=%d",
        template.code,
        len(feats),
        len(tags),
    )
    return FeatureVector(
        owner_id=template.id,
        owner_kind="activity_template",
        features=dict(sorted(feats.items())),
    )


def persist_resident_vector(
    matching_repo: MatchingRepository,
    vector: FeatureVector,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> None:
    """Upsert each feature weight to ``resident_feature_weights``."""
    if vector.owner_kind != "resident":
        raise ValueError(
            f"persist_resident_vector requires a resident vector, got {vector.owner_kind!r}"
        )
    for feature_key, weight in vector.features.items():
        matching_repo.upsert_resident_feature_weight(
            resident_id=vector.owner_id,
            feature_key=feature_key,
            feature_weight=weight,
            model_version=model_version,
        )


def persist_template_vector(
    matching_repo: MatchingRepository,
    vector: FeatureVector,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> None:
    """Upsert each feature weight to ``activity_feature_weights``.

    The ``activity_id`` column accepts template ids since migration 003
    relaxed the foreign key for matching-artifact tables.
    """
    if vector.owner_kind != "activity_template":
        raise ValueError(
            f"persist_template_vector requires a template vector, got {vector.owner_kind!r}"
        )
    for feature_key, weight in vector.features.items():
        matching_repo.upsert_activity_feature_weight(
            activity_id=vector.owner_id,
            feature_key=feature_key,
            feature_weight=weight,
            model_version=model_version,
        )
