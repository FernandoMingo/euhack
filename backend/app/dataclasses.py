from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ResidentStatus = Literal["active", "paused", "withdrawn"]
VerificationStatus = Literal["pending", "approved", "rejected"]
VerificationOutcome = Literal["passed", "failed"]
CaptureMethod = Literal["in_consult", "self_completion"]
ReferralStatus = Literal["submitted", "accepted", "closed"]
ConsentStatus = Literal["active", "revoked"]
ActivityRisk = Literal["low", "medium", "high"]
ApprovalStatus = Literal["draft", "proposed", "approved", "rejected"]
CircleStatus = Literal["proposed", "invitations_sent", "confirmed", "completed", "cancelled"]
InvitationStatus = Literal["sent", "accepted", "declined", "expired"]
AttendanceStatus = Literal["invited", "attended", "no_show"]
DecisionType = Literal["approved", "rejected", "edited"]
RunType = Literal["activity_ranking", "circle_matching", "re_recommendation"]
GraphEntityType = Literal["resident", "activity", "circle", "host", "venue", "resident_internal"]
FlagType = Literal["outlier", "retaliation_suspected", "spam_pattern", "abusive_text"]
FlagSeverity = Literal["low", "medium", "high"]


@dataclass(slots=True)
class Resident:
    id: str
    first_name: str
    email: str
    preferred_language: str
    city: str
    neighborhood: str | None
    location_radius_km: int
    social_comfort: str
    preferred_group_size_min: int
    preferred_group_size_max: int
    cost_sensitivity: str
    status: ResidentStatus
    created_at: datetime
    updated_at: datetime
    withdrawn_at: datetime | None = None


@dataclass(slots=True)
class TrustedProfessional:
    id: str
    full_name: str
    role: str
    organization: str | None
    city: str | None
    email: str
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime
    agb_code: str | None = None
    big_number: str | None = None
    qualification: str | None = None
    onderneming_agb_code: str | None = None
    verified_at: datetime | None = None


@dataclass(slots=True)
class ProfessionalVerification:
    id: str
    professional_id: str
    outcome: VerificationOutcome
    created_at: datetime
    agb_response_json: str | None = None
    big_response_json: str | None = None
    kvk_response_json: str | None = None
    failure_reason: str | None = None


@dataclass(slots=True)
class ResidentPreference:
    id: str
    resident_id: str
    preference_type: Literal["interest", "activity", "accessibility_need"]
    value: str
    created_at: datetime


@dataclass(slots=True)
class ResidentAvailability:
    id: str
    resident_id: str
    weekday: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    start_time_local: str
    end_time_local: str
    created_at: datetime


@dataclass(slots=True)
class ResidentAvoidance:
    id: str
    resident_id: str
    value: str
    created_at: datetime


@dataclass(slots=True)
class Referral:
    id: str
    resident_id: str
    professional_id: str
    referral_reason: str | None
    status: ReferralStatus
    created_at: datetime
    closed_at: datetime | None = None


@dataclass(slots=True)
class ConsentRecord:
    id: str
    resident_id: str
    professional_id: str
    status: ConsentStatus
    granted_at: datetime
    created_at: datetime
    consent_text_version: str = "v1.0-nl-2026-05"
    consent_locale: str = "nl"
    capture_method: CaptureMethod = "in_consult"
    revoked_at: datetime | None = None


@dataclass(slots=True)
class ConsentScope:
    id: str
    consent_id: str
    scope: Literal[
        "create_social_profile",
        "use_profile_for_activity_matching",
        "send_activity_invitations",
        "share_limited_status_with_professional",
        "internal_peer_ratings",
    ]


@dataclass(slots=True)
class Venue:
    id: str
    name: str
    address: str
    city: str
    lat: float | None
    lng: float | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Host:
    id: str
    full_name: str
    contact_email: str | None
    host_type: Literal["volunteer", "city_staff", "partner_staff", "facilitator"]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Activity:
    id: str
    title: str
    activity_type: str
    venue_id: str
    host_id: str | None
    start_at: datetime
    end_at: datetime
    capacity: int
    cost_cents: int
    risk_level: ActivityRisk
    approval_status: ApprovalStatus
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Circle:
    id: str
    status: CircleStatus
    fit_score: float | None
    shared_signals_json: str
    created_at: datetime
    updated_at: datetime
    activity_id: str | None = None
    template_id: str | None = None


@dataclass(slots=True)
class CircleMember:
    id: str
    circle_id: str
    resident_id: str
    joined_at: datetime


@dataclass(slots=True)
class Invitation:
    id: str
    circle_id: str
    activity_id: str
    resident_id: str
    status: InvitationStatus
    companion_pass_used: bool
    sent_at: datetime
    responded_at: datetime | None = None


@dataclass(slots=True)
class AttendanceEvent:
    id: str
    activity_id: str
    resident_id: str
    attendance_status: AttendanceStatus
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None


@dataclass(slots=True)
class CircleRevealEvent:
    id: str
    activity_id: str
    resident_id: str
    revealed_at: datetime


@dataclass(slots=True)
class ResidentFeedback:
    id: str
    activity_id: str
    resident_id: str
    felt_after: Literal["worse", "same", "better"] | None
    activity_fit: bool | None
    group_comfort: bool | None
    would_repeat: bool | None
    safety_reported: bool
    notes: str | None
    created_at: datetime


@dataclass(slots=True)
class OperatorDecision:
    id: str
    activity_id: str
    operator_id: str
    decision: DecisionType
    reason: str | None
    created_at: datetime


@dataclass(slots=True)
class MatchingRun:
    id: str
    run_type: RunType
    model_version: str
    score_algorithm: str
    created_at: datetime
    source_window_start: datetime | None = None
    source_window_end: datetime | None = None


@dataclass(slots=True)
class MatchCandidate:
    id: str
    matching_run_id: str
    resident_id: str | None
    circle_id: str | None
    activity_id: str | None
    total_score: float
    rank_position: int
    hard_constraints_passed: bool
    created_at: datetime


@dataclass(slots=True)
class MatchFeatureScore:
    id: str
    match_candidate_id: str
    feature_key: str
    feature_weight: float
    feature_score: float
    contribution: float
    created_at: datetime


@dataclass(slots=True)
class MatchExplanation:
    id: str
    match_candidate_id: str
    summary_text: str
    explanation_json: str
    created_at: datetime


@dataclass(slots=True)
class FeatureWeight:
    id: str
    feature_key: str
    feature_weight: float
    model_version: str
    computed_at: datetime
    resident_id: str | None = None
    activity_id: str | None = None


@dataclass(slots=True)
class ResidentActivitySimilarity:
    id: str
    resident_id: str
    activity_id: str
    algorithm: str
    model_version: str
    similarity_score: float
    computed_at: datetime


@dataclass(slots=True)
class GraphEdge:
    id: str
    src_type: GraphEntityType
    src_id: str
    dst_type: GraphEntityType
    dst_id: str
    edge_type: str
    edge_weight: float
    created_at: datetime


@dataclass(slots=True)
class GraphScore:
    id: str
    entity_type: Literal["activity", "circle", "host", "venue", "resident_internal"]
    entity_id: str
    algorithm: str
    model_version: str
    score: float
    computed_at: datetime
    sample_size: int | None = None


@dataclass(slots=True)
class PeerRating:
    id: str
    activity_id: str
    rater_resident_id: str
    ratee_resident_id: str
    comfort_to_be_with: int | None
    respectful_behavior: int | None
    reliability_showed_up: int | None
    group_contribution: int | None
    note_text: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class PeerRatingRollup:
    id: str
    resident_id: str
    model_version: str
    comfort_to_be_with_score: float | None
    respectful_behavior_score: float | None
    reliability_showed_up_score: float | None
    group_contribution_score: float | None
    rating_count: int
    confidence: float | None
    recentness_weighted_score: float | None
    computed_at: datetime


@dataclass(slots=True)
class PeerRatingFlag:
    id: str
    peer_rating_id: str
    flag_type: FlagType
    severity: FlagSeverity
    details: str | None
    created_at: datetime


@dataclass(slots=True)
class SafetyReport:
    id: str
    activity_id: str
    report_type: str
    escalation_level: Literal["none", "operator_review", "urgent"]
    created_at: datetime
    reporter_resident_id: str | None = None
    description: str | None = None


@dataclass(slots=True)
class AuditEvent:
    id: str
    actor_type: Literal["resident", "professional", "operator", "system"]
    action: str
    entity_type: str
    metadata_json: str
    created_at: datetime
    actor_id: str | None = None
    entity_id: str | None = None


CostBand = Literal["free", "low", "medium", "high"]
SocialEnergy = Literal["low", "medium", "high"]
Setting = Literal["indoor", "outdoor", "mixed"]
Intensity = Literal["still", "light", "active", "vigorous"]
NoiseLevel = Literal["quiet", "moderate", "loud"]
StructureType = Literal["guided", "self_paced", "mixed"]


@dataclass(slots=True)
class ActivityTemplate:
    id: str
    code: str
    title: str
    description: str
    family: str
    typical_duration_minutes: int
    typical_group_size_min: int
    typical_group_size_max: int
    typical_cost_band: CostBand
    social_energy: SocialEnergy
    setting: Setting
    intensity: Intensity
    noise_level: NoiseLevel
    structure: StructureType
    risk_level: ActivityRisk
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ActivityTemplateTag:
    id: str
    template_id: str
    tag: str


@dataclass(slots=True)
class RankingSnapshot:
    """
    Internal read model for ranking and matching diagnostics.
    """

    resident_id: str
    activity_id: str
    model_version: str
    cosine_similarity: float | None = None
    graph_score: float | None = None
    peer_rollup_score: float | None = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
    feature_contributions: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RankingInput:
    resident: Resident
    activities: list[Activity]
    resident_feature_weights: list[FeatureWeight]
    activity_feature_weights: list[FeatureWeight]
    peer_rollup: PeerRatingRollup | None = None
    graph_scores: list[GraphScore] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

