"""
dataclass-to-pydantic conversion helpers.

The dataclasses in app.dataclasses model database rows; the pydantic
models in app.api.schemas model the wire format. Keeping the conversion
in one place lets each side evolve independently.
"""

from __future__ import annotations

from app.api import schemas
from app.dataclasses import (
    Activity,
    ActivityTemplate,
    AttendanceEvent,
    Circle,
    CircleMember,
    ConsentRecord,
    ConsentScope,
    Host,
    Invitation,
    MatchCandidate,
    MatchingRun,
    PeerRating,
    PeerRatingFlag,
    PeerRatingRollup,
    ProfessionalVerification,
    Referral,
    Resident,
    ResidentAvailability,
    ResidentAvoidance,
    ResidentFeedback,
    ResidentPreference,
    TrustedProfessional,
    Venue,
)


def professional_to_response(p: TrustedProfessional) -> schemas.ProfessionalResponse:
    return schemas.ProfessionalResponse(
        id=p.id,
        full_name=p.full_name,
        role=p.role,
        organization=p.organization,
        city=p.city,
        email=p.email,
        verification_status=p.verification_status,
        agb_code=p.agb_code,
        big_number=p.big_number,
        qualification=p.qualification,
        onderneming_agb_code=p.onderneming_agb_code,
        verified_at=p.verified_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def verification_to_response(v: ProfessionalVerification) -> schemas.VerificationRecordResponse:
    return schemas.VerificationRecordResponse(
        id=v.id,
        professional_id=v.professional_id,
        outcome=v.outcome,
        failure_reason=v.failure_reason,
        created_at=v.created_at,
    )


def resident_to_response(r: Resident) -> schemas.ResidentResponse:
    return schemas.ResidentResponse(
        id=r.id,
        first_name=r.first_name,
        email=r.email,
        preferred_language=r.preferred_language,
        city=r.city,
        neighborhood=r.neighborhood,
        location_radius_km=r.location_radius_km,
        social_comfort=r.social_comfort,
        preferred_group_size_min=r.preferred_group_size_min,
        preferred_group_size_max=r.preferred_group_size_max,
        cost_sensitivity=r.cost_sensitivity,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def consent_to_response(
    c: ConsentRecord,
    scopes: list[ConsentScope],
) -> schemas.ConsentResponse:
    return schemas.ConsentResponse(
        id=c.id,
        resident_id=c.resident_id,
        professional_id=c.professional_id,
        status=c.status,
        granted_at=c.granted_at,
        consent_text_version=c.consent_text_version,
        consent_locale=c.consent_locale,
        capture_method=c.capture_method,
        scopes=[s.scope for s in scopes],  # type: ignore[misc]
    )


def referral_to_response(r: Referral) -> schemas.ReferralResponse:
    return schemas.ReferralResponse(
        id=r.id,
        resident_id=r.resident_id,
        professional_id=r.professional_id,
        referral_reason=r.referral_reason,
        status=r.status,
        created_at=r.created_at,
    )


def preference_to_response(p: ResidentPreference) -> schemas.ResidentPreferenceResponse:
    return schemas.ResidentPreferenceResponse(
        id=p.id,
        resident_id=p.resident_id,
        preference_type=p.preference_type,
        value=p.value,
        created_at=p.created_at,
    )


def availability_to_response(a: ResidentAvailability) -> schemas.ResidentAvailabilityResponse:
    return schemas.ResidentAvailabilityResponse(
        id=a.id,
        resident_id=a.resident_id,
        weekday=a.weekday,
        start_time_local=a.start_time_local,
        end_time_local=a.end_time_local,
        created_at=a.created_at,
    )


def avoidance_to_response(a: ResidentAvoidance) -> schemas.ResidentAvoidanceResponse:
    return schemas.ResidentAvoidanceResponse(
        id=a.id,
        resident_id=a.resident_id,
        value=a.value,
        created_at=a.created_at,
    )


def template_to_response(
    t: ActivityTemplate,
    tags: list[str] | None = None,
) -> schemas.ActivityTemplateResponse:
    return schemas.ActivityTemplateResponse(
        id=t.id,
        code=t.code,
        title=t.title,
        description=t.description,
        family=t.family,
        typical_duration_minutes=t.typical_duration_minutes,
        typical_group_size_min=t.typical_group_size_min,
        typical_group_size_max=t.typical_group_size_max,
        typical_cost_band=t.typical_cost_band,
        social_energy=t.social_energy,
        setting=t.setting,
        intensity=t.intensity,
        noise_level=t.noise_level,
        structure=t.structure,
        risk_level=t.risk_level,
        tags=tags or [],
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def venue_to_response(v: Venue) -> schemas.VenueResponse:
    return schemas.VenueResponse(
        id=v.id,
        name=v.name,
        address=v.address,
        city=v.city,
        lat=v.lat,
        lng=v.lng,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


def host_to_response(h: Host) -> schemas.HostResponse:
    return schemas.HostResponse(
        id=h.id,
        full_name=h.full_name,
        contact_email=h.contact_email,
        host_type=h.host_type,
        created_at=h.created_at,
        updated_at=h.updated_at,
    )


def activity_to_response(a: Activity) -> schemas.ActivityResponse:
    return schemas.ActivityResponse(
        id=a.id,
        title=a.title,
        activity_type=a.activity_type,
        venue_id=a.venue_id,
        host_id=a.host_id,
        start_at=a.start_at,
        end_at=a.end_at,
        capacity=a.capacity,
        cost_cents=a.cost_cents,
        risk_level=a.risk_level,
        approval_status=a.approval_status,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def circle_to_response(c: Circle) -> schemas.CircleResponse:
    return schemas.CircleResponse(
        id=c.id,
        activity_id=c.activity_id,
        template_id=c.template_id,
        status=c.status,
        fit_score=c.fit_score,
        shared_signals_json=c.shared_signals_json,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def circle_member_to_response(m: CircleMember) -> schemas.CircleMemberResponse:
    return schemas.CircleMemberResponse(
        id=m.id,
        circle_id=m.circle_id,
        resident_id=m.resident_id,
        joined_at=m.joined_at,
    )


def invitation_to_response(i: Invitation) -> schemas.InvitationResponse:
    return schemas.InvitationResponse(
        id=i.id,
        circle_id=i.circle_id,
        activity_id=i.activity_id,
        resident_id=i.resident_id,
        status=i.status,
        companion_pass_used=i.companion_pass_used,
        sent_at=i.sent_at,
        responded_at=i.responded_at,
    )


def attendance_to_response(a: AttendanceEvent) -> schemas.AttendanceResponse:
    return schemas.AttendanceResponse(
        id=a.id,
        activity_id=a.activity_id,
        resident_id=a.resident_id,
        attendance_status=a.attendance_status,
        check_in_at=a.check_in_at,
        check_out_at=a.check_out_at,
    )


def feedback_to_response(f: ResidentFeedback) -> schemas.FeedbackResponse:
    return schemas.FeedbackResponse(
        id=f.id,
        activity_id=f.activity_id,
        resident_id=f.resident_id,
        felt_after=f.felt_after,
        activity_fit=f.activity_fit,
        group_comfort=f.group_comfort,
        would_repeat=f.would_repeat,
        safety_reported=f.safety_reported,
        notes=f.notes,
        created_at=f.created_at,
    )


def matching_run_to_response(r: MatchingRun) -> schemas.MatchingRunResponse:
    return schemas.MatchingRunResponse(
        id=r.id,
        run_type=r.run_type,
        model_version=r.model_version,
        score_algorithm=r.score_algorithm,
        source_window_start=r.source_window_start,
        source_window_end=r.source_window_end,
        created_at=r.created_at,
    )


def match_candidate_to_response(c: MatchCandidate) -> schemas.MatchCandidateResponse:
    return schemas.MatchCandidateResponse(
        id=c.id,
        matching_run_id=c.matching_run_id,
        resident_id=c.resident_id,
        circle_id=c.circle_id,
        activity_id=c.activity_id,
        total_score=c.total_score,
        rank_position=c.rank_position,
        hard_constraints_passed=c.hard_constraints_passed,
        created_at=c.created_at,
    )


def peer_rating_to_response(p: PeerRating) -> schemas.PeerRatingResponse:
    return schemas.PeerRatingResponse(
        id=p.id,
        activity_id=p.activity_id,
        rater_resident_id=p.rater_resident_id,
        ratee_resident_id=p.ratee_resident_id,
        comfort_to_be_with=p.comfort_to_be_with,
        respectful_behavior=p.respectful_behavior,
        reliability_showed_up=p.reliability_showed_up,
        group_contribution=p.group_contribution,
        note_text=p.note_text,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def peer_rollup_to_response(r: PeerRatingRollup) -> schemas.PeerRatingRollupResponse:
    return schemas.PeerRatingRollupResponse(
        id=r.id,
        resident_id=r.resident_id,
        model_version=r.model_version,
        comfort_to_be_with_score=r.comfort_to_be_with_score,
        respectful_behavior_score=r.respectful_behavior_score,
        reliability_showed_up_score=r.reliability_showed_up_score,
        group_contribution_score=r.group_contribution_score,
        rating_count=r.rating_count,
        confidence=r.confidence,
        recentness_weighted_score=r.recentness_weighted_score,
        computed_at=r.computed_at,
    )


def peer_flag_to_response(f: PeerRatingFlag) -> schemas.PeerRatingFlagResponse:
    return schemas.PeerRatingFlagResponse(
        id=f.id,
        peer_rating_id=f.peer_rating_id,
        flag_type=f.flag_type,
        severity=f.severity,
        details=f.details,
        created_at=f.created_at,
    )
