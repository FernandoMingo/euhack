"""Deterministic people/group matching (circle formation) v1.

Reuses the Feature 5 vectorizer, hard constraints, and scoring helpers
to form small compatible resident groups ("circles") around a single
activity template or an approved activity. The engine is intentionally
deterministic and explainable:

1. Resolve the target template (and optional concrete activity).
2. Pull candidate residents (defaults to ``status='active'`` residents).
3. For each candidate, vectorize and evaluate the same hard constraints
   the activity-ranking engine uses (avoidances, cost band, group-size
   range, social-energy fit, accessibility). Residents that fail are
   recorded as filtered candidates with the reasons preserved.
4. Sort eligible residents by their resident -> template score
   descending, tie-break by resident id, then form groups greedily:
   start with the highest-fit seed, accept compatible residents (shared
   availability buckets, every member's preferred group-size range
   still admits the new size) until ``max_group_size`` is hit or no
   more compatible residents remain. Each resident can appear in at
   most one proposed circle per run.
5. Score every group on a fixed weighted combination of
   - mean resident -> template fit (template_fit),
   - density of shared availability buckets (availability_density),
   - intersection of high-weight interest / theme features
     (interest_overlap),
   - how close the group size lies to each member's preferred
     mid-point (group_size_comfort), and
   - how uniform the members' social-energy levels are
     (social_energy_consistency).
   The final score is in ``[0, 1]`` and is tie-broken on the sorted
   tuple of member ids for reproducibility.
6. Persist a ``matching_runs`` row with ``run_type='circle_matching'``
   plus a ``circles`` + ``circle_members`` + ``match_candidates`` +
   ``match_feature_scores`` + ``match_explanations`` chain for every
   accepted group, plus a rejected ``match_candidates`` +
   ``match_explanations`` pair for every filtered resident. No
   invitations are sent and no peer-rating data is read here.

The implementation only uses Python's standard library and the existing
repositories/dataclasses.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from typing import Iterable

from app.dataclasses import (
    Activity,
    ActivityTemplate,
    Circle,
    CircleMember,
    Resident,
    ResidentAvailability,
    ResidentAvoidance,
    ResidentPreference,
)
from app.matching.constraints import ConstraintResult, check_template_constraints
from app.matching.scoring import (
    ScoreBreakdown,
    availability_overlap_score,
    cosine_similarity,
    cost_compatibility_score,
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
    social_energy_from_comfort,
)
from app.repositories.activity_repository import ActivityRepository
from app.repositories.activity_template_repository import ActivityTemplateRepository
from app.repositories.matching_repository import MatchingRepository
from app.repositories.resident_repository import ResidentRepository

logger = logging.getLogger(__name__)

_DEFAULT_MIN_GROUP_SIZE = 3
_DEFAULT_MAX_GROUP_SIZE = 6
_DEFAULT_TOP_N = 3
_SCORE_ALGORITHM = "circle_greedy_v1"

# Final group-fit weight model. Sums to 1.0 so the result stays in
# ``[0, 1]`` even before clamping.
_W_TEMPLATE_FIT = 0.50
_W_AVAILABILITY = 0.20
_W_INTEREST = 0.15
_W_GROUP_SIZE = 0.10
_W_SOCIAL_ENERGY = 0.05

_AVAILABILITY_SATURATION = 3.0  # 3+ shared buckets -> max availability density
_INTEREST_SATURATION = 3.0      # 3+ shared interest/theme keys -> max overlap
_INTEREST_PREFIXES: tuple[str, ...] = ("interest:", "theme:", "attribute:")
_TOP_FEATURE_COUNT = 5


@dataclass(slots=True, frozen=True)
class _ResidentProfile:
    """Per-resident derived state used while forming groups."""

    resident: Resident
    vector: FeatureVector
    preferences: tuple[ResidentPreference, ...]
    availabilities: tuple[ResidentAvailability, ...]
    avoidances: tuple[ResidentAvoidance, ...]
    template_score: ScoreBreakdown
    availability_buckets: frozenset[str]
    interest_keys: frozenset[str]
    social_energy: str  # "low" | "medium" | "high"
    constraint: ConstraintResult
    fairness_priority: float = 0.0
    recent_success_count: int = 0


@dataclass(slots=True, frozen=True)
class GroupComponents:
    """Group-level signals that compose the fit score."""

    template_fit: float
    availability_density: float
    interest_overlap: float
    group_size_comfort: float
    social_energy_consistency: float


@dataclass(slots=True, frozen=True)
class ProposedGroup:
    """An accepted candidate circle returned to callers."""

    members: tuple[Resident, ...]
    member_template_scores: tuple[float, ...]
    components: GroupComponents
    fit_score: float
    shared_availability: tuple[str, ...]
    shared_interests: tuple[str, ...]
    summary_text: str
    payload: dict[str, object]
    circle: Circle | None = None
    circle_members: tuple[CircleMember, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class RejectedResident:
    """A resident that failed hard constraints for this template."""

    resident: Resident
    reasons: tuple[str, ...]
    summary_text: str
    payload: dict[str, object]


@dataclass(slots=True, frozen=True)
class UnmatchedResident:
    """An eligible resident that was not placed in a proposed circle."""

    resident: Resident
    reason: str
    summary_text: str
    payload: dict[str, object]


@dataclass(slots=True, frozen=True)
class GroupingResult:
    """Public return value of :meth:`CircleEngine.run_grouping`."""

    matching_run_id: str
    template: ActivityTemplate
    activity: Activity | None
    groups: tuple[ProposedGroup, ...]
    rejected: tuple[RejectedResident, ...]
    unmatched: tuple[UnmatchedResident, ...] = tuple()


# ---------------------------------------------------------------------------
# Pure helpers (no DB access).
# ---------------------------------------------------------------------------


def shared_availability_buckets(
    profiles: Iterable[_ResidentProfile],
) -> frozenset[str]:
    """Intersection of every profile's availability buckets."""
    iterator = iter(profiles)
    try:
        first = next(iterator)
    except StopIteration:
        return frozenset()
    shared: frozenset[str] = first.availability_buckets
    for profile in iterator:
        shared = shared & profile.availability_buckets
        if not shared:
            return shared
    return shared


def shared_interest_keys(
    profiles: Iterable[_ResidentProfile],
) -> frozenset[str]:
    """Intersection of positive interest/theme/attribute feature keys."""
    iterator = iter(profiles)
    try:
        first = next(iterator)
    except StopIteration:
        return frozenset()
    shared: frozenset[str] = first.interest_keys
    for profile in iterator:
        shared = shared & profile.interest_keys
        if not shared:
            return shared
    return shared


def availability_density(shared_buckets: int) -> float:
    """Map the count of shared buckets to ``[0, 1]`` (saturates at 3)."""
    if shared_buckets <= 0:
        return 0.0
    if shared_buckets >= _AVAILABILITY_SATURATION:
        return 1.0
    return shared_buckets / _AVAILABILITY_SATURATION


def interest_overlap_score(shared_interest_count: int) -> float:
    """Map shared interest count to ``[0, 1]`` (saturates at 3)."""
    if shared_interest_count <= 0:
        return 0.0
    if shared_interest_count >= _INTEREST_SATURATION:
        return 1.0
    return shared_interest_count / _INTEREST_SATURATION


def group_size_comfort(group_size: int, profiles: list[_ResidentProfile]) -> float:
    """Mean comfort over members: 1 when ``group_size`` sits inside each
    member's preferred range, decaying linearly when it falls outside."""
    if not profiles:
        return 0.0
    comforts: list[float] = []
    for profile in profiles:
        lo = profile.resident.preferred_group_size_min
        hi = profile.resident.preferred_group_size_max
        if lo <= group_size <= hi:
            comforts.append(1.0)
            continue
        if group_size < lo:
            distance = lo - group_size
        else:
            distance = group_size - hi
        # Tolerate two-person deviation before the comfort hits zero.
        comforts.append(max(0.0, 1.0 - distance / 2.0))
    return sum(comforts) / len(comforts)


def social_energy_consistency(profiles: list[_ResidentProfile]) -> float:
    """1.0 when all members share a social-energy level, decaying by 0.4
    per additional distinct level. Three different levels still score
    above zero (0.2) so a mixed-but-non-clashing group is acceptable."""
    if not profiles:
        return 0.0
    distinct = {profile.social_energy for profile in profiles}
    return max(0.0, 1.0 - (len(distinct) - 1) * 0.4)


def compute_group_fit(
    profiles: list[_ResidentProfile],
) -> tuple[float, GroupComponents, frozenset[str], frozenset[str]]:
    """Pure score function: returns (fit_score, components, shared_avail, shared_interests)."""
    if not profiles:
        zero = GroupComponents(
            template_fit=0.0,
            availability_density=0.0,
            interest_overlap=0.0,
            group_size_comfort=0.0,
            social_energy_consistency=0.0,
        )
        return 0.0, zero, frozenset(), frozenset()

    template_fit = sum(p.template_score.total for p in profiles) / len(profiles)
    shared_avail = shared_availability_buckets(profiles)
    shared_interests = shared_interest_keys(profiles)
    avail_score = availability_density(len(shared_avail))
    interest_score = interest_overlap_score(len(shared_interests))
    size_score = group_size_comfort(len(profiles), profiles)
    energy_score = social_energy_consistency(profiles)

    total = (
        _W_TEMPLATE_FIT * template_fit
        + _W_AVAILABILITY * avail_score
        + _W_INTEREST * interest_score
        + _W_GROUP_SIZE * size_score
        + _W_SOCIAL_ENERGY * energy_score
    )
    if total < 0.0:
        total = 0.0
    if total > 1.0:
        total = 1.0
    return (
        total,
        GroupComponents(
            template_fit=template_fit,
            availability_density=avail_score,
            interest_overlap=interest_score,
            group_size_comfort=size_score,
            social_energy_consistency=energy_score,
        ),
        shared_avail,
        shared_interests,
    )


# ---------------------------------------------------------------------------
# Engine.
# ---------------------------------------------------------------------------


class CircleEngine:
    """Forms small compatible circles around an activity template or activity.

    Implementation reuses the Feature 5 vectorizer and constraint
    checker so a resident filtered out for ranking is also filtered out
    for circle membership, with the same reason strings.
    """

    def __init__(
        self,
        *,
        residents: ResidentRepository,
        templates: ActivityTemplateRepository,
        matching: MatchingRepository,
        activities: ActivityRepository,
        model_version: str = DEFAULT_MODEL_VERSION,
        score_algorithm: str = _SCORE_ALGORITHM,
        fair_grouping: bool = False,
    ) -> None:
        self.residents = residents
        self.templates = templates
        self.matching = matching
        self.activities = activities
        self.model_version = model_version
        self.score_algorithm = score_algorithm
        self.fair_grouping = fair_grouping

    def run_grouping(
        self,
        *,
        template_code: str | None = None,
        template_id: str | None = None,
        activity_id: str | None = None,
        resident_ids: list[str] | None = None,
        top_n: int = _DEFAULT_TOP_N,
        min_group_size: int = _DEFAULT_MIN_GROUP_SIZE,
        max_group_size: int = _DEFAULT_MAX_GROUP_SIZE,
        persist: bool = True,
    ) -> GroupingResult:
        """Execute one circle-matching run. Returns groups + rejected residents.

        Exactly one of ``template_code``, ``template_id`` or
        ``activity_id`` should be supplied (``activity_id`` implies the
        operator has already approved a concrete activity; the template
        is then inferred from the activity's ``activity_type`` code).
        """
        if min_group_size < 2:
            raise ValueError("min_group_size must be >= 2")
        if max_group_size < min_group_size:
            raise ValueError("max_group_size must be >= min_group_size")
        if top_n < 1:
            raise ValueError("top_n must be >= 1")

        template, activity = self._resolve_target(
            template_code=template_code,
            template_id=template_id,
            activity_id=activity_id,
        )
        tags = self.templates.get_tags(template.id)
        template_vector = build_template_vector(template, tags)

        candidate_residents = self._load_residents(resident_ids)

        eligible: list[_ResidentProfile] = []
        rejected_profiles: list[_ResidentProfile] = []
        for resident in candidate_residents:
            profile = self._build_profile(
                resident=resident,
                template=template,
                template_tags=tags,
                template_vector=template_vector,
            )
            if profile.constraint.passed:
                eligible.append(profile)
            else:
                rejected_profiles.append(profile)

        if self.fair_grouping:
            eligible.sort(
                key=lambda p: (
                    -p.fairness_priority,
                    -p.template_score.total,
                    p.resident.id,
                )
            )
        else:
            eligible.sort(
                key=lambda p: (-p.template_score.total, p.resident.id)
            )

        proposed = self._form_groups(
            eligible_profiles=eligible,
            min_group_size=min_group_size,
            max_group_size=max_group_size,
        )

        ranked_groups = sorted(
            proposed,
            key=lambda item: (
                -item[0],
                tuple(p.resident.id for p in item[1]),
            ),
        )[:top_n]
        grouped_ids = {
            profile.resident.id
            for _, profiles, _, _, _ in proposed
            for profile in profiles
        }
        ungrouped_profiles = (
            [profile for profile in eligible if profile.resident.id not in grouped_ids]
            if self.fair_grouping
            else []
        )

        run_id = ""
        accepted_groups: list[ProposedGroup] = []
        rejected_residents: list[RejectedResident] = []
        unmatched_residents: list[UnmatchedResident] = []
        if persist:
            run_id, accepted_groups, rejected_residents, unmatched_residents = self._persist_run(
                template=template,
                activity=activity,
                template_vector=template_vector,
                ranked_groups=ranked_groups,
                rejected_profiles=rejected_profiles,
                eligible_profiles=eligible,
                ungrouped_profiles=ungrouped_profiles,
            )
        else:
            for rank, (fit_score, profiles, components, shared_avail, shared_int) in enumerate(
                ranked_groups, start=1
            ):
                accepted_groups.append(
                    _build_proposed_group(
                        rank=rank,
                        fit_score=fit_score,
                        components=components,
                        profiles=profiles,
                        shared_avail=shared_avail,
                        shared_interests=shared_int,
                        model_version=self.model_version,
                        template=template,
                        activity=activity,
                    )
                )
            for offset, profile in enumerate(
                sorted(rejected_profiles, key=lambda p: p.resident.id),
                start=len(accepted_groups) + 1,
            ):
                rejected_residents.append(
                    _build_rejected_resident(
                        rank=offset,
                        profile=profile,
                        model_version=self.model_version,
                        template=template,
                    )
                )
            for offset, profile in enumerate(
                sorted(ungrouped_profiles, key=lambda p: p.resident.id),
                start=len(accepted_groups) + len(rejected_residents) + 1,
            ):
                unmatched_residents.append(
                    _build_unmatched_resident(
                        rank=offset,
                        profile=profile,
                        model_version=self.model_version,
                        template=template,
                        reason="eligible_not_grouped",
                    )
                )

        logger.info(
            "circle_matching.run end run=%s template=%s groups=%d rejected=%d eligible=%d",
            run_id or "(unpersisted)",
            template.code,
            len(accepted_groups),
            len(rejected_residents),
            len(eligible),
        )

        return GroupingResult(
            matching_run_id=run_id,
            template=template,
            activity=activity,
            groups=tuple(accepted_groups),
            rejected=tuple(rejected_residents),
            unmatched=tuple(unmatched_residents),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_target(
        self,
        *,
        template_code: str | None,
        template_id: str | None,
        activity_id: str | None,
    ) -> tuple[ActivityTemplate, Activity | None]:
        provided = [x for x in (template_code, template_id, activity_id) if x]
        if not provided:
            raise ValueError(
                "run_grouping requires one of template_code, template_id, activity_id"
            )
        activity: Activity | None = None
        if activity_id is not None:
            activity = self.activities.get_activity(activity_id)
            if activity is None:
                raise ValueError(f"Activity {activity_id} not found")
            template_code = template_code or activity.activity_type

        template: ActivityTemplate | None = None
        if template_id is not None:
            for candidate in self.templates.list_templates():
                if candidate.id == template_id:
                    template = candidate
                    break
            if template is None:
                raise ValueError(f"Template {template_id} not found")
        elif template_code is not None:
            template = self.templates.get_template_by_code(template_code)
            if template is None:
                raise ValueError(f"Template code {template_code!r} not found")
        if template is None:
            raise ValueError(
                "Unable to resolve target template from inputs"
            )
        return template, activity

    def _load_residents(self, resident_ids: list[str] | None) -> list[Resident]:
        if resident_ids is None:
            return self.residents.list_residents(status="active")
        seen: set[str] = set()
        residents: list[Resident] = []
        for rid in resident_ids:
            if rid in seen:
                continue
            seen.add(rid)
            resident = self.residents.get_resident(rid)
            if resident is None:
                logger.warning("circle_matching.resident_missing id=%s", rid)
                continue
            residents.append(resident)
        residents.sort(key=lambda r: r.id)
        return residents

    def _build_profile(
        self,
        *,
        resident: Resident,
        template: ActivityTemplate,
        template_tags: list[str],
        template_vector: FeatureVector,
    ) -> _ResidentProfile:
        preferences = self.residents.list_preferences(resident_id=resident.id)
        availabilities = self.residents.list_availabilities(resident_id=resident.id)
        avoidances = self.residents.list_avoidances(resident_id=resident.id)

        vector = build_resident_vector(resident, preferences, availabilities, avoidances)

        availability_buckets: set[str] = set()
        for avail in availabilities:
            for bucket in availability_buckets_for_window(
                avail.start_time_local, avail.end_time_local
            ):
                availability_buckets.add(f"{avail.weekday}_{bucket}")

        access_needs = [
            pref.value
            for pref in preferences
            if pref.preference_type == "accessibility_need"
        ]
        constraint = check_template_constraints(
            resident=resident,
            avoidances=list(avoidances),
            template=template,
            template_tags=template_tags,
            accessibility_needs=access_needs,
        )
        if resident.status != "active":
            extra_reasons = (f"resident_status:{resident.status}",)
            constraint = ConstraintResult(
                passed=False,
                reasons=extra_reasons + constraint.reasons,
            )

        cosine = cosine_similarity(vector.features, template_vector.features)
        cost = cost_compatibility_score(
            allowed_cost_bands(resident.cost_sensitivity), template.typical_cost_band
        )
        avail_signal = availability_overlap_score(availability_buckets)
        breakdown = weighted_total(
            cosine=cosine,
            cost_score=cost,
            availability_score=avail_signal,
        )

        interest_keys = {
            key
            for key, weight in vector.features.items()
            if weight > 0.0
            and any(key.startswith(prefix) for prefix in _INTEREST_PREFIXES)
        }

        return _ResidentProfile(
            resident=resident,
            vector=vector,
            preferences=tuple(preferences),
            availabilities=tuple(availabilities),
            avoidances=tuple(avoidances),
            template_score=breakdown,
            availability_buckets=frozenset(availability_buckets),
            interest_keys=frozenset(interest_keys),
            social_energy=social_energy_from_comfort(resident.social_comfort),
            constraint=constraint,
            fairness_priority=self._fairness_priority(resident.id),
            recent_success_count=self.activities.count_recent_successful_matches(
                resident_id=resident.id
            )
            if self.fair_grouping
            else 0,
        )

    def _fairness_priority(self, resident_id: str) -> float:
        if not self.fair_grouping:
            return 0.0
        successes = self.activities.count_recent_successful_matches(
            resident_id=resident_id
        )
        return 1.0 / (1.0 + successes)

    def _form_groups(
        self,
        *,
        eligible_profiles: list[_ResidentProfile],
        min_group_size: int,
        max_group_size: int,
    ) -> list[tuple[float, list[_ResidentProfile], GroupComponents, frozenset[str], frozenset[str]]]:
        """Greedy seed-and-grow grouping. Each resident is used at most once."""
        if not eligible_profiles:
            return []

        remaining = list(eligible_profiles)
        groups: list[
            tuple[float, list[_ResidentProfile], GroupComponents, frozenset[str], frozenset[str]]
        ] = []

        while remaining:
            seed = remaining.pop(0)
            current_group: list[_ResidentProfile] = [seed]
            current_avail: frozenset[str] = seed.availability_buckets
            pool = list(remaining)

            # Effective group-size cap is the intersection of every member's
            # preferred-group-size range, bounded by ``max_group_size``.
            effective_max = min(max_group_size, seed.resident.preferred_group_size_max)
            effective_min = max(min_group_size, seed.resident.preferred_group_size_min)

            while pool and len(current_group) < effective_max:
                next_addition: _ResidentProfile | None = None
                for profile in pool:
                    if not profile.availability_buckets:
                        continue
                    new_avail = current_avail & profile.availability_buckets
                    if not new_avail:
                        continue
                    new_max = min(
                        effective_max, profile.resident.preferred_group_size_max
                    )
                    new_min = max(
                        effective_min, profile.resident.preferred_group_size_min
                    )
                    if len(current_group) + 1 > new_max:
                        continue
                    if new_min > new_max:
                        continue
                    next_addition = profile
                    break
                if next_addition is None:
                    break
                current_group.append(next_addition)
                pool.remove(next_addition)
                remaining.remove(next_addition)
                current_avail = current_avail & next_addition.availability_buckets
                effective_max = min(
                    effective_max, next_addition.resident.preferred_group_size_max
                )
                effective_min = max(
                    effective_min, next_addition.resident.preferred_group_size_min
                )

            if len(current_group) < effective_min or len(current_group) < min_group_size:
                continue
            if len(current_group) > effective_max:
                continue

            fit_score, components, shared_avail, shared_interests = compute_group_fit(
                current_group
            )
            if self.fair_grouping:
                member_scores = [p.template_score.total for p in current_group]
                min_fit = min(member_scores)
                spread = max(member_scores) - min_fit
                fit_score = max(0.0, min(1.0, fit_score * 0.75 + min_fit * 0.25 - spread * 0.10))
            groups.append(
                (fit_score, current_group, components, shared_avail, shared_interests)
            )
        return groups

    def _persist_run(
        self,
        *,
        template: ActivityTemplate,
        activity: Activity | None,
        template_vector: FeatureVector,
        ranked_groups: list[
            tuple[float, list[_ResidentProfile], GroupComponents, frozenset[str], frozenset[str]]
        ],
        rejected_profiles: list[_ResidentProfile],
        eligible_profiles: list[_ResidentProfile],
        ungrouped_profiles: list[_ResidentProfile],
    ) -> tuple[
        str,
        list[ProposedGroup],
        list[RejectedResident],
        list[UnmatchedResident],
    ]:
        run = self.matching.create_matching_run(
            run_type="circle_matching",
            model_version=self.model_version,
            score_algorithm=self.score_algorithm,
        )
        logger.info(
            "circle_matching.run start id=%s template=%s eligible=%d rejected=%d",
            run.id,
            template.code,
            len(eligible_profiles),
            len(rejected_profiles),
        )
        persist_template_vector(self.matching, template_vector, self.model_version)
        seen_residents: set[str] = set()
        for profile in eligible_profiles + rejected_profiles:
            if profile.resident.id in seen_residents:
                continue
            seen_residents.add(profile.resident.id)
            persist_resident_vector(self.matching, profile.vector, self.model_version)

        accepted: list[ProposedGroup] = []
        for rank, (fit_score, profiles, components, shared_avail, shared_interests) in enumerate(
            ranked_groups, start=1
        ):
            group = _build_proposed_group(
                rank=rank,
                fit_score=fit_score,
                components=components,
                profiles=profiles,
                shared_avail=shared_avail,
                shared_interests=shared_interests,
                model_version=self.model_version,
                template=template,
                activity=activity,
            )
            circle = self.activities.create_circle(
                activity_id=activity.id if activity is not None else None,
                template_id=template.id if activity is None else None,
                status="proposed",
                fit_score=round(fit_score, 6),
                shared_signals_json=json.dumps(
                    {
                        "shared_availability": sorted(shared_avail),
                        "shared_interests": sorted(shared_interests),
                    },
                    sort_keys=True,
                ),
            )
            members: list[CircleMember] = []
            for profile in profiles:
                members.append(
                    self.activities.add_circle_member(
                        circle_id=circle.id,
                        resident_id=profile.resident.id,
                    )
                )
            candidate = self.matching.add_match_candidate(
                matching_run_id=run.id,
                circle_id=circle.id,
                activity_id=activity.id if activity is not None else template.id,
                total_score=fit_score,
                rank_position=rank,
                hard_constraints_passed=True,
            )
            for feature_key, weight in _group_feature_scores(components, profiles):
                self.matching.add_feature_score(
                    match_candidate_id=candidate.id,
                    feature_key=feature_key,
                    feature_weight=weight["weight"],
                    feature_score=weight["score"],
                    contribution=weight["contribution"],
                )
            self.matching.add_explanation(
                match_candidate_id=candidate.id,
                summary_text=group.summary_text,
                explanation_json=json.dumps(group.payload, sort_keys=True),
            )

            group = dataclasses.replace(
                group,
                circle=circle,
                circle_members=tuple(members),
            )
            accepted.append(group)
            logger.info(
                "circle_matching.group rank=%d circle=%s fit=%.4f size=%d",
                rank,
                circle.id,
                fit_score,
                len(profiles),
            )

        rejected: list[RejectedResident] = []
        rank_cursor = len(accepted) + 1
        for profile in sorted(rejected_profiles, key=lambda p: p.resident.id):
            rejected_resident = _build_rejected_resident(
                rank=rank_cursor,
                profile=profile,
                model_version=self.model_version,
                template=template,
            )
            candidate = self.matching.add_match_candidate(
                matching_run_id=run.id,
                resident_id=profile.resident.id,
                activity_id=activity.id if activity is not None else template.id,
                total_score=profile.template_score.total,
                rank_position=rank_cursor,
                hard_constraints_passed=False,
            )
            self.matching.add_explanation(
                match_candidate_id=candidate.id,
                summary_text=rejected_resident.summary_text,
                explanation_json=json.dumps(rejected_resident.payload, sort_keys=True),
            )
            rejected.append(rejected_resident)
            rank_cursor += 1

        unmatched: list[UnmatchedResident] = []
        for profile in sorted(ungrouped_profiles, key=lambda p: p.resident.id):
            unmatched_resident = _build_unmatched_resident(
                rank=rank_cursor,
                profile=profile,
                model_version=self.model_version,
                template=template,
                reason="eligible_not_grouped",
            )
            candidate = self.matching.add_match_candidate(
                matching_run_id=run.id,
                resident_id=profile.resident.id,
                activity_id=activity.id if activity is not None else template.id,
                total_score=profile.template_score.total,
                rank_position=rank_cursor,
                hard_constraints_passed=True,
            )
            self.matching.add_explanation(
                match_candidate_id=candidate.id,
                summary_text=unmatched_resident.summary_text,
                explanation_json=json.dumps(unmatched_resident.payload, sort_keys=True),
            )
            unmatched.append(unmatched_resident)
            rank_cursor += 1

        self.matching.conn.commit()
        return run.id, accepted, rejected, unmatched


# ---------------------------------------------------------------------------
# Pure builders used by both the persisted and in-memory return paths.
# ---------------------------------------------------------------------------


def _build_proposed_group(
    *,
    rank: int,
    fit_score: float,
    components: GroupComponents,
    profiles: list[_ResidentProfile],
    shared_avail: frozenset[str],
    shared_interests: frozenset[str],
    model_version: str,
    template: ActivityTemplate,
    activity: Activity | None,
) -> ProposedGroup:
    member_residents = tuple(p.resident for p in profiles)
    member_scores = tuple(round(p.template_score.total, 6) for p in profiles)
    shared_avail_list = sorted(shared_avail)
    shared_interest_list = sorted(shared_interests)[:_TOP_FEATURE_COUNT]
    names = ", ".join(p.resident.first_name for p in profiles)
    avail_hint = (
        shared_avail_list[0].replace("_", " ")
        if shared_avail_list
        else "shared time slot"
    )
    interest_hint = (
        shared_interest_list[0].split(":", 1)[1].replace("_", " ")
        if shared_interest_list and ":" in shared_interest_list[0]
        else "shared interests"
    )
    summary = (
        f"#{rank} Circle for {template.title} — {len(profiles)} residents "
        f"({names}). Fit {fit_score:.2f} on {avail_hint}, {interest_hint}."
    )
    payload: dict[str, object] = {
        "model_version": model_version,
        "template_code": template.code,
        "template_id": template.id,
        "activity_id": activity.id if activity is not None else None,
        "rank_position": rank,
        "fit_score": round(fit_score, 6),
        "group_size": len(profiles),
        "components": {
            "template_fit": round(components.template_fit, 6),
            "availability_density": round(components.availability_density, 6),
            "interest_overlap": round(components.interest_overlap, 6),
            "group_size_comfort": round(components.group_size_comfort, 6),
            "social_energy_consistency": round(
                components.social_energy_consistency, 6
            ),
        },
        "members": [
            {
                "resident_id": p.resident.id,
                "first_name": p.resident.first_name,
                "template_score": round(p.template_score.total, 6),
                "cosine": round(p.template_score.cosine, 6),
                "social_energy": p.social_energy,
            }
            for p in profiles
        ],
        "shared_availability": shared_avail_list,
        "shared_interests": shared_interest_list,
        "constraints": {"passed": True, "reasons": []},
    }
    return ProposedGroup(
        members=member_residents,
        member_template_scores=member_scores,
        components=components,
        fit_score=fit_score,
        shared_availability=tuple(shared_avail_list),
        shared_interests=tuple(shared_interest_list),
        summary_text=summary,
        payload=payload,
        circle=None,
        circle_members=tuple(),
    )


def _build_rejected_resident(
    *,
    rank: int,
    profile: _ResidentProfile,
    model_version: str,
    template: ActivityTemplate,
) -> RejectedResident:
    reasons = profile.constraint.reasons
    reason_text = "; ".join(reasons) if reasons else "constraint failed"
    summary = (
        f"#{rank} {profile.resident.first_name}: filtered out of "
        f"{template.title} ({reason_text})."
    )
    payload: dict[str, object] = {
        "model_version": model_version,
        "template_code": template.code,
        "template_id": template.id,
        "rank_position": rank,
        "resident_id": profile.resident.id,
        "constraints": {"passed": False, "reasons": list(reasons)},
        "template_score": round(profile.template_score.total, 6),
    }
    return RejectedResident(
        resident=profile.resident,
        reasons=reasons,
        summary_text=summary,
        payload=payload,
    )


def _build_unmatched_resident(
    *,
    rank: int,
    profile: _ResidentProfile,
    model_version: str,
    template: ActivityTemplate,
    reason: str,
) -> UnmatchedResident:
    summary = (
        f"#{rank} {profile.resident.first_name}: eligible for {template.title} "
        f"but not placed ({reason})."
    )
    payload: dict[str, object] = {
        "model_version": model_version,
        "template_code": template.code,
        "template_id": template.id,
        "rank_position": rank,
        "resident_id": profile.resident.id,
        "constraints": {"passed": True, "reasons": []},
        "unmatched_reason": reason,
        "template_score": round(profile.template_score.total, 6),
        "fairness_priority": round(profile.fairness_priority, 6),
        "recent_success_count": profile.recent_success_count,
    }
    return UnmatchedResident(
        resident=profile.resident,
        reason=reason,
        summary_text=summary,
        payload=payload,
    )


def _group_feature_scores(
    components: GroupComponents,
    profiles: list[_ResidentProfile],
) -> list[tuple[str, dict[str, float]]]:
    """Return the ``match_feature_scores`` rows describing the group fit."""
    rows: list[tuple[str, dict[str, float]]] = [
        (
            "group:template_fit",
            {
                "weight": _W_TEMPLATE_FIT,
                "score": components.template_fit,
                "contribution": _W_TEMPLATE_FIT * components.template_fit,
            },
        ),
        (
            "group:availability_density",
            {
                "weight": _W_AVAILABILITY,
                "score": components.availability_density,
                "contribution": _W_AVAILABILITY * components.availability_density,
            },
        ),
        (
            "group:interest_overlap",
            {
                "weight": _W_INTEREST,
                "score": components.interest_overlap,
                "contribution": _W_INTEREST * components.interest_overlap,
            },
        ),
        (
            "group:group_size_comfort",
            {
                "weight": _W_GROUP_SIZE,
                "score": components.group_size_comfort,
                "contribution": _W_GROUP_SIZE * components.group_size_comfort,
            },
        ),
        (
            "group:social_energy_consistency",
            {
                "weight": _W_SOCIAL_ENERGY,
                "score": components.social_energy_consistency,
                "contribution": _W_SOCIAL_ENERGY * components.social_energy_consistency,
            },
        ),
    ]
    if profiles:
        scores = [p.template_score.total for p in profiles]
        spread = max(scores) - min(scores)
        rows.append(
            (
                "group:template_fit_spread",
                {
                    "weight": 0.0,
                    "score": round(spread, 6),
                    "contribution": 0.0,
                },
            )
        )
    return rows


__all__ = [
    "CircleEngine",
    "GroupComponents",
    "GroupingResult",
    "ProposedGroup",
    "RejectedResident",
    "UnmatchedResident",
    "availability_density",
    "compute_group_fit",
    "group_size_comfort",
    "interest_overlap_score",
    "shared_availability_buckets",
    "shared_interest_keys",
    "social_energy_consistency",
]
