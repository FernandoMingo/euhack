"""Matching engine orchestrator.

Owns the full lifecycle of an activity ranking run:

1. Load the resident's structured state (profile, prefs, availability,
   avoidances) and build a sparse feature vector.
2. For every activity template, build its feature vector, evaluate hard
   constraints, and score the survivors.
3. Persist:
   * resident / template feature weights (``model_version='v1'``)
   * a ``matching_runs`` row (``run_type='activity_ranking'``,
     ``score_algorithm='cosine_weighted'``)
   * one ``match_candidates`` row per template (passing + filtered),
     with ``hard_constraints_passed`` reflecting the result
   * per-feature contributions in ``match_feature_scores`` for passing
     candidates only
   * ``match_explanations`` summary + structured JSON for every candidate
   * ``resident_activity_similarity`` cosine cache (passing candidates)
4. Return the top-N passing candidates ordered by ``rank_position`` plus
   the matching run id.

Side effects live only in this module and the repositories; pure scoring
logic stays in :mod:`app.matching.scoring`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterable

from app.dataclasses import ActivityTemplate, MatchCandidate
from app.matching.constraints import ConstraintResult, check_template_constraints
from app.matching.explain import Explanation, build_explanation
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
    FeatureVector,
    allowed_cost_bands,
    availability_buckets_for_window,
    build_resident_vector,
    build_template_vector,
    persist_resident_vector,
    persist_template_vector,
)
from app.repositories.activity_template_repository import ActivityTemplateRepository
from app.repositories.matching_repository import MatchingRepository
from app.repositories.resident_repository import ResidentRepository

logger = logging.getLogger(__name__)

_DEFAULT_TOP_N = 5
_FEATURE_SCORES_PER_CANDIDATE = 10


@dataclass(slots=True, frozen=True)
class MatchResult:
    """Per-candidate result returned to callers (top-N slice)."""

    template: ActivityTemplate
    candidate: MatchCandidate
    breakdown: ScoreBreakdown
    contributions: dict[str, float]
    constraint: ConstraintResult
    explanation: Explanation


@dataclass(slots=True)
class _ScoredTemplate:
    template: ActivityTemplate
    template_vector: FeatureVector
    breakdown: ScoreBreakdown
    contributions: dict[str, float]
    constraint: ConstraintResult


class MatchingEngine:
    """High level orchestrator that wires repositories + pure functions together."""

    def __init__(
        self,
        *,
        residents: ResidentRepository,
        templates: ActivityTemplateRepository,
        matching: MatchingRepository,
        model_version: str = DEFAULT_MODEL_VERSION,
        score_algorithm: str = "cosine_weighted",
    ) -> None:
        self.residents = residents
        self.templates = templates
        self.matching = matching
        self.model_version = model_version
        self.score_algorithm = score_algorithm

    def run_matching(
        self,
        *,
        resident_id: str,
        top_n: int = _DEFAULT_TOP_N,
        persist_vectors: bool = True,
        templates: Iterable[ActivityTemplate] | None = None,
    ) -> tuple[str, list[MatchResult]]:
        """Execute one matching run for a resident; return (run_id, top results)."""
        resident = self.residents.get_resident(resident_id)
        if resident is None:
            raise ValueError(f"Resident {resident_id} not found")

        preferences = self.residents.list_preferences(resident_id=resident_id)
        availabilities = self.residents.list_availabilities(resident_id=resident_id)
        avoidances = self.residents.list_avoidances(resident_id=resident_id)

        resident_vector = build_resident_vector(
            resident, preferences, availabilities, avoidances
        )
        if persist_vectors:
            persist_resident_vector(self.matching, resident_vector, self.model_version)

        template_list = list(templates) if templates is not None else self.templates.list_templates()
        if not template_list:
            logger.info(
                "matching.run skipped resident=%s reason=no_templates", resident.id
            )
            return "", []

        run = self.matching.create_matching_run(
            run_type="activity_ranking",
            model_version=self.model_version,
            score_algorithm=self.score_algorithm,
        )
        logger.info(
            "matching.run start id=%s resident=%s templates=%d model_version=%s",
            run.id,
            resident.id,
            len(template_list),
            self.model_version,
        )

        access_needs = [
            pref.value
            for pref in preferences
            if pref.preference_type == "accessibility_need"
        ]
        allowed_bands = allowed_cost_bands(resident.cost_sensitivity)
        availability_buckets: set[str] = set()
        for avail in availabilities:
            for bucket in availability_buckets_for_window(
                avail.start_time_local, avail.end_time_local
            ):
                availability_buckets.add(f"{avail.weekday}_{bucket}")
        avail_score = availability_overlap_score(availability_buckets)

        scored: list[_ScoredTemplate] = []
        for template in template_list:
            tags = self.templates.get_tags(template.id)
            template_vector = build_template_vector(template, tags)
            if persist_vectors:
                persist_template_vector(self.matching, template_vector, self.model_version)

            constraint = check_template_constraints(
                resident=resident,
                avoidances=avoidances,
                template=template,
                template_tags=tags,
                accessibility_needs=access_needs,
            )
            cosine = cosine_similarity(resident_vector.features, template_vector.features)
            cost = cost_compatibility_score(allowed_bands, template.typical_cost_band)
            breakdown = weighted_total(
                cosine=cosine,
                cost_score=cost,
                availability_score=avail_score,
            )
            contribs = feature_contributions(
                resident_vector.features, template_vector.features
            )
            scored.append(
                _ScoredTemplate(
                    template=template,
                    template_vector=template_vector,
                    breakdown=breakdown,
                    contributions=contribs,
                    constraint=constraint,
                )
            )

        passing = [item for item in scored if item.constraint.passed]
        passing.sort(key=lambda item: (-item.breakdown.total, item.template.code))
        rejected = sorted(
            (item for item in scored if not item.constraint.passed),
            key=lambda item: item.template.code,
        )

        results: list[MatchResult] = []
        for rank, item in enumerate(passing, start=1):
            results.append(
                self._persist_candidate(
                    run_id=run.id,
                    resident_id=resident.id,
                    item=item,
                    rank=rank,
                    resident_vector=resident_vector,
                    record_feature_scores=True,
                    update_similarity=True,
                )
            )

        for offset, item in enumerate(rejected, start=1):
            self._persist_candidate(
                run_id=run.id,
                resident_id=resident.id,
                item=item,
                rank=len(passing) + offset,
                resident_vector=resident_vector,
                record_feature_scores=False,
                update_similarity=False,
            )

        if results:
            top = results[0]
            logger.info(
                "matching.run top resident=%s template=%s total=%.4f cosine=%.4f",
                resident.id,
                top.template.code,
                top.breakdown.total,
                top.breakdown.cosine,
            )
        logger.info(
            "matching.run end id=%s passed=%d rejected=%d",
            run.id,
            len(passing),
            len(rejected),
        )

        self.matching.conn.commit()
        return run.id, results[:top_n]

    def _persist_candidate(
        self,
        *,
        run_id: str,
        resident_id: str,
        item: _ScoredTemplate,
        rank: int,
        resident_vector: FeatureVector,
        record_feature_scores: bool,
        update_similarity: bool,
    ) -> MatchResult:
        candidate = self.matching.add_match_candidate(
            matching_run_id=run_id,
            resident_id=resident_id,
            activity_id=item.template.id,
            total_score=item.breakdown.total,
            rank_position=rank,
            hard_constraints_passed=item.constraint.passed,
        )

        if record_feature_scores:
            top_contribs = sorted(
                item.contributions.items(),
                key=lambda kv: (-kv[1], kv[0]),
            )[:_FEATURE_SCORES_PER_CANDIDATE]
            for feature_key, contribution in top_contribs:
                self.matching.add_feature_score(
                    match_candidate_id=candidate.id,
                    feature_key=feature_key,
                    feature_weight=resident_vector.features.get(feature_key, 0.0),
                    feature_score=item.template_vector.features.get(feature_key, 0.0),
                    contribution=contribution,
                )

        explanation = build_explanation(
            template_title=item.template.title,
            template_code=item.template.code,
            rank_position=rank,
            model_version=self.model_version,
            breakdown=item.breakdown,
            contributions=item.contributions,
            constraint_passed=item.constraint.passed,
            constraint_reasons=item.constraint.reasons,
        )
        self.matching.add_explanation(
            match_candidate_id=candidate.id,
            summary_text=explanation.summary_text,
            explanation_json=json.dumps(explanation.payload, sort_keys=True),
        )

        if update_similarity:
            self.matching.upsert_similarity(
                resident_id=resident_id,
                activity_id=item.template.id,
                algorithm="cosine",
                model_version=self.model_version,
                similarity_score=item.breakdown.cosine,
            )

        return MatchResult(
            template=item.template,
            candidate=candidate,
            breakdown=item.breakdown,
            contributions=item.contributions,
            constraint=item.constraint,
            explanation=explanation,
        )
