"""Deterministic vectorizer and matching engine for CivicCircles.

This package converts residents and activity templates into a shared sparse
feature space, ranks templates by cosine similarity plus soft signals, and
persists every step (vectors, scores, explanations, similarity cache) so
operators can audit any recommendation.
"""

from app.matching.constraints import ConstraintResult, check_template_constraints
from app.matching.engine import MatchingEngine, MatchResult
from app.matching.explain import Explanation, build_explanation
from app.matching.grouping import (
    CircleEngine,
    GroupComponents,
    GroupingResult,
    ProposedGroup,
    RejectedResident,
    availability_density,
    compute_group_fit,
    group_size_comfort,
    interest_overlap_score,
    shared_availability_buckets,
    shared_interest_keys,
    social_energy_consistency,
)
from app.matching.scoring import (
    ScoreBreakdown,
    availability_overlap_score,
    cosine_similarity,
    cost_compatibility_score,
    feature_contributions,
    weighted_total,
)
from app.matching.vectorizer import (
    DEFAULT_MODEL_VERSION,
    AVOIDANCE_WEIGHT,
    FeatureVector,
    allowed_cost_bands,
    availability_buckets_for_window,
    build_resident_vector,
    build_template_vector,
    persist_resident_vector,
    persist_template_vector,
    social_energy_from_comfort,
)

__all__ = [
    "AVOIDANCE_WEIGHT",
    "CircleEngine",
    "ConstraintResult",
    "DEFAULT_MODEL_VERSION",
    "Explanation",
    "FeatureVector",
    "GroupComponents",
    "GroupingResult",
    "MatchResult",
    "MatchingEngine",
    "ProposedGroup",
    "RejectedResident",
    "ScoreBreakdown",
    "allowed_cost_bands",
    "availability_buckets_for_window",
    "availability_density",
    "availability_overlap_score",
    "build_explanation",
    "build_resident_vector",
    "build_template_vector",
    "check_template_constraints",
    "compute_group_fit",
    "cosine_similarity",
    "cost_compatibility_score",
    "feature_contributions",
    "group_size_comfort",
    "interest_overlap_score",
    "persist_resident_vector",
    "persist_template_vector",
    "shared_availability_buckets",
    "shared_interest_keys",
    "social_energy_consistency",
    "social_energy_from_comfort",
    "weighted_total",
]
