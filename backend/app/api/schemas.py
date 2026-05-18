"""
Pydantic request/response models for the CivicCircles API.

These mirror the dataclasses in app.dataclasses one-for-one: the
dataclasses model database rows, the pydantic models model the wire
format, and the two are free to diverge.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# ---------- Shared literal aliases ----------

CaptureMethodLiteral = Literal["in_consult", "self_completion"]
VerificationStatusLiteral = Literal["pending", "approved", "rejected"]
VerificationOutcomeLiteral = Literal["passed", "failed"]
ResidentStatusLiteral = Literal["active", "paused", "withdrawn"]
ReferralStatusLiteral = Literal["submitted", "accepted", "closed"]
ConsentStatusLiteral = Literal["active", "revoked"]
InvitationStatusLiteral = Literal["sent", "accepted", "declined", "expired"]
AttendanceStatusLiteral = Literal["invited", "attended", "no_show"]
ApprovalStatusLiteral = Literal["draft", "proposed", "approved", "rejected"]
CircleStatusLiteral = Literal["proposed", "invitations_sent", "confirmed", "completed", "cancelled"]
ActivityRiskLiteral = Literal["low", "medium", "high"]
WeekdayLiteral = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PreferenceTypeLiteral = Literal["interest", "activity", "accessibility_need"]
HostTypeLiteral = Literal["volunteer", "city_staff", "partner_staff", "facilitator"]
RunTypeLiteral = Literal["activity_ranking", "circle_matching", "re_recommendation"]
FeltAfterLiteral = Literal["worse", "same", "better"]
FlagTypeLiteral = Literal["outlier", "retaliation_suspected", "spam_pattern", "abusive_text"]
FlagSeverityLiteral = Literal["low", "medium", "high"]

ConsentScopeLiteral = Literal[
    "create_social_profile",
    "use_profile_for_activity_matching",
    "send_activity_invitations",
    "share_limited_status_with_professional",
    "internal_peer_ratings",
]


# ---------- Professional signup / read ----------


class ProfessionalSignupRequest(BaseModel):
    full_name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    email: EmailStr
    agb_code: str = Field(min_length=8, max_length=8)
    big_number: str | None = None
    kvk_number: str | None = None
    organization: str | None = None
    city: str | None = None
    qualification_hint: str | None = None


class ProfessionalResponse(BaseModel):
    id: str
    full_name: str
    role: str
    organization: str | None
    city: str | None
    email: str
    verification_status: VerificationStatusLiteral
    agb_code: str | None
    big_number: str | None
    qualification: str | None
    onderneming_agb_code: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VerificationRecordResponse(BaseModel):
    id: str
    professional_id: str
    outcome: VerificationOutcomeLiteral
    failure_reason: str | None
    created_at: datetime


class ProfessionalSignupResponse(BaseModel):
    professional: ProfessionalResponse
    verification: VerificationRecordResponse


# ---------- Resident referral ----------


class AvailabilityWindow(BaseModel):
    weekday: WeekdayLiteral
    start_time_local: str
    end_time_local: str


class ResidentProfilePayload(BaseModel):
    first_name: str = Field(min_length=1)
    email: EmailStr
    preferred_language: str = Field(min_length=1)
    city: str = Field(min_length=1)
    social_comfort: str = Field(min_length=1)
    preferred_group_size_min: int = Field(ge=1)
    preferred_group_size_max: int = Field(ge=1)
    cost_sensitivity: str = Field(min_length=1)
    neighborhood: str | None = None
    location_radius_km: int = Field(default=3, ge=0)
    interests: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)
    availability: list[AvailabilityWindow] = Field(default_factory=list)
    avoidances: list[str] = Field(default_factory=list)


class ReferralRequest(BaseModel):
    professional_id: str = Field(min_length=1)
    profile: ResidentProfilePayload
    consent_scopes: list[ConsentScopeLiteral] = Field(
        default_factory=lambda: [
            "create_social_profile",
            "use_profile_for_activity_matching",
            "send_activity_invitations",
            "share_limited_status_with_professional",
        ]
    )
    consent_text_version: str = "v1.0-nl-2026-05"
    consent_locale: str = "nl"
    capture_method: CaptureMethodLiteral = "in_consult"
    referral_reason: str | None = None


class ResidentResponse(BaseModel):
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
    status: ResidentStatusLiteral
    created_at: datetime
    updated_at: datetime


class ConsentResponse(BaseModel):
    id: str
    resident_id: str
    professional_id: str
    status: ConsentStatusLiteral
    granted_at: datetime
    consent_text_version: str
    consent_locale: str
    capture_method: CaptureMethodLiteral
    scopes: list[ConsentScopeLiteral]


class ReferralResponse(BaseModel):
    id: str
    resident_id: str
    professional_id: str
    referral_reason: str | None
    status: ReferralStatusLiteral
    created_at: datetime


class ReferralCreateResponse(BaseModel):
    resident: ResidentResponse
    consent: ConsentResponse
    referral: ReferralResponse


class ReferralStatusUpdateRequest(BaseModel):
    status: ReferralStatusLiteral


# ---------- Resident updates (preferences, availability, avoidances, status) ----------


class ResidentStatusUpdateRequest(BaseModel):
    status: ResidentStatusLiteral


class ResidentPreferenceRequest(BaseModel):
    preference_type: PreferenceTypeLiteral
    value: str = Field(min_length=1)


class ResidentPreferenceResponse(BaseModel):
    id: str
    resident_id: str
    preference_type: PreferenceTypeLiteral
    value: str
    created_at: datetime


class ResidentAvailabilityRequest(BaseModel):
    weekday: WeekdayLiteral
    start_time_local: str
    end_time_local: str


class ResidentAvailabilityResponse(BaseModel):
    id: str
    resident_id: str
    weekday: WeekdayLiteral
    start_time_local: str
    end_time_local: str
    created_at: datetime


class ResidentAvoidanceRequest(BaseModel):
    value: str = Field(min_length=1)


class ResidentAvoidanceResponse(BaseModel):
    id: str
    resident_id: str
    value: str
    created_at: datetime


# ---------- Activity templates (catalog) ----------


class ActivityTemplateResponse(BaseModel):
    id: str
    code: str
    title: str
    description: str
    family: str
    typical_duration_minutes: int
    typical_group_size_min: int
    typical_group_size_max: int
    typical_cost_band: Literal["free", "low", "medium", "high"]
    social_energy: Literal["low", "medium", "high"]
    setting: Literal["indoor", "outdoor", "mixed"]
    intensity: Literal["still", "light", "active", "vigorous"]
    noise_level: Literal["quiet", "moderate", "loud"]
    structure: Literal["guided", "self_paced", "mixed"]
    risk_level: ActivityRiskLiteral
    tags: list[str]
    created_at: datetime
    updated_at: datetime


# ---------- Activities (real instances), venues, hosts, circles ----------


class VenueCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    lat: float | None = None
    lng: float | None = None


class VenueResponse(BaseModel):
    id: str
    name: str
    address: str
    city: str
    lat: float | None
    lng: float | None
    created_at: datetime
    updated_at: datetime


class HostCreateRequest(BaseModel):
    full_name: str = Field(min_length=1)
    host_type: HostTypeLiteral
    contact_email: EmailStr | None = None


class HostResponse(BaseModel):
    id: str
    full_name: str
    contact_email: str | None
    host_type: HostTypeLiteral
    created_at: datetime
    updated_at: datetime


class ActivityCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    activity_type: str = Field(min_length=1)
    venue_id: str = Field(min_length=1)
    start_at: datetime
    end_at: datetime
    capacity: int = Field(ge=1)
    risk_level: ActivityRiskLiteral
    approval_status: ApprovalStatusLiteral
    host_id: str | None = None
    cost_cents: int = Field(default=0, ge=0)


class ActivityResponse(BaseModel):
    id: str
    title: str
    activity_type: str
    venue_id: str
    host_id: str | None
    start_at: datetime
    end_at: datetime
    capacity: int
    cost_cents: int
    risk_level: ActivityRiskLiteral
    approval_status: ApprovalStatusLiteral
    created_at: datetime
    updated_at: datetime


class CircleCreateRequest(BaseModel):
    status: CircleStatusLiteral = "proposed"
    fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    shared_signals_json: str = "[]"


class CircleResponse(BaseModel):
    id: str
    activity_id: str
    status: CircleStatusLiteral
    fit_score: float | None
    shared_signals_json: str
    created_at: datetime
    updated_at: datetime


class CircleMemberCreateRequest(BaseModel):
    resident_id: str = Field(min_length=1)


class CircleMemberResponse(BaseModel):
    id: str
    circle_id: str
    resident_id: str
    joined_at: datetime


# ---------- Invitations ----------


class InvitationCreateRequest(BaseModel):
    circle_id: str = Field(min_length=1)
    activity_id: str = Field(min_length=1)
    resident_id: str = Field(min_length=1)
    status: InvitationStatusLiteral = "sent"


class InvitationDecisionRequest(BaseModel):
    companion_pass_used: bool = False


class InvitationResponse(BaseModel):
    id: str
    circle_id: str
    activity_id: str
    resident_id: str
    status: InvitationStatusLiteral
    companion_pass_used: bool
    sent_at: datetime
    responded_at: datetime | None


# ---------- Attendance + feedback ----------


class AttendanceRequest(BaseModel):
    resident_id: str = Field(min_length=1)
    attendance_status: AttendanceStatusLiteral
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None


class AttendanceResponse(BaseModel):
    id: str
    activity_id: str
    resident_id: str
    attendance_status: AttendanceStatusLiteral
    check_in_at: datetime | None
    check_out_at: datetime | None


class FeedbackRequest(BaseModel):
    resident_id: str = Field(min_length=1)
    felt_after: FeltAfterLiteral | None = None
    activity_fit: bool | None = None
    group_comfort: bool | None = None
    would_repeat: bool | None = None
    safety_reported: bool = False
    notes: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    activity_id: str
    resident_id: str
    felt_after: FeltAfterLiteral | None
    activity_fit: bool | None
    group_comfort: bool | None
    would_repeat: bool | None
    safety_reported: bool
    notes: str | None
    created_at: datetime


# ---------- Matching (operator-only) ----------


class MatchingRunCreateRequest(BaseModel):
    run_type: RunTypeLiteral
    model_version: str = Field(min_length=1)
    score_algorithm: str = Field(min_length=1)
    source_window_start: datetime | None = None
    source_window_end: datetime | None = None


class MatchingRunResponse(BaseModel):
    id: str
    run_type: RunTypeLiteral
    model_version: str
    score_algorithm: str
    source_window_start: datetime | None
    source_window_end: datetime | None
    created_at: datetime


class MatchCandidateCreateRequest(BaseModel):
    total_score: float
    rank_position: int = Field(ge=1)
    hard_constraints_passed: bool
    resident_id: str | None = None
    circle_id: str | None = None
    activity_id: str | None = None


class MatchCandidateResponse(BaseModel):
    id: str
    matching_run_id: str
    resident_id: str | None
    circle_id: str | None
    activity_id: str | None
    total_score: float
    rank_position: int
    hard_constraints_passed: bool
    created_at: datetime


# ---------- Peer ratings (operator/internal-only) ----------


class PeerRatingCreateRequest(BaseModel):
    activity_id: str = Field(min_length=1)
    rater_resident_id: str = Field(min_length=1)
    ratee_resident_id: str = Field(min_length=1)
    comfort_to_be_with: int | None = Field(default=None, ge=1, le=5)
    respectful_behavior: int | None = Field(default=None, ge=1, le=5)
    reliability_showed_up: int | None = Field(default=None, ge=1, le=5)
    group_contribution: int | None = Field(default=None, ge=1, le=5)
    note_text: str | None = None


class PeerRatingResponse(BaseModel):
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


class PeerRatingRollupRequest(BaseModel):
    resident_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    comfort_to_be_with_score: float | None = None
    respectful_behavior_score: float | None = None
    reliability_showed_up_score: float | None = None
    group_contribution_score: float | None = None
    rating_count: int = Field(default=0, ge=0)
    confidence: float | None = None
    recentness_weighted_score: float | None = None


class PeerRatingRollupResponse(BaseModel):
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


class PeerRatingFlagRequest(BaseModel):
    flag_type: FlagTypeLiteral
    severity: FlagSeverityLiteral
    details: str | None = None


class PeerRatingFlagResponse(BaseModel):
    id: str
    peer_rating_id: str
    flag_type: FlagTypeLiteral
    severity: FlagSeverityLiteral
    details: str | None
    created_at: datetime
