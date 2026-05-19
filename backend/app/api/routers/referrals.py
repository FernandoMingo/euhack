from __future__ import annotations

import logging
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import schemas
from app.api.converters import (
    consent_to_response,
    referral_to_response,
    resident_to_response,
)
from app.api.deps import get_connection, get_email_client
from app.repositories import ConsentRepository, ReferralRepository
from app.services import MatchingWorkflowService
from app.services.email_client import EmailClient
from app.services.onboarding_service import OnboardingService, ResidentProfileInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


def _avail_tuple(window: schemas.AvailabilityWindow) -> tuple[str, str, str]:
    return (window.weekday, window.start_time_local, window.end_time_local)


@router.post(
    "",
    response_model=schemas.ReferralCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_referral(
    payload: schemas.ReferralRequest,
    conn: Connection = Depends(get_connection),
    email_client: EmailClient | None = Depends(get_email_client),
) -> schemas.ReferralCreateResponse:
    """Create a referral and, in demo mode, immediately produce an invitation.

    After the resident + consent + referral rows are persisted, we run the
    deterministic matching workflow on the new referral and auto-approve
    the resulting circle so the resident receives the invitation email
    right away — no manual seed script, no operator click required.

    The auto-flow is best-effort: if matching can't form a circle (empty
    pool, no templates, etc.) the response still returns 201 with the
    referral, just without an attached invitation.
    """
    service = OnboardingService(conn)
    profile = payload.profile
    try:
        result = service.create_referral(
            professional_id=payload.professional_id,
            profile=ResidentProfileInput(
                first_name=profile.first_name,
                email=profile.email,
                preferred_language=profile.preferred_language,
                city=profile.city,
                social_comfort=profile.social_comfort,
                preferred_group_size_min=profile.preferred_group_size_min,
                preferred_group_size_max=profile.preferred_group_size_max,
                cost_sensitivity=profile.cost_sensitivity,
                neighborhood=profile.neighborhood,
                location_radius_km=profile.location_radius_km,
                interests=tuple(profile.interests),
                activities=tuple(profile.activities),
                accessibility_needs=tuple(profile.accessibility_needs),
                availability=tuple(_avail_tuple(a) for a in profile.availability),
                avoidances=tuple(profile.avoidances),
            ),
            consent_scopes=payload.consent_scopes,
            referral_reason=payload.referral_reason,
            consent_text_version=payload.consent_text_version,
            consent_locale=payload.consent_locale,
            capture_method=payload.capture_method,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    scopes = ConsentRepository(conn).list_scopes(result.consent.id)

    # --- Auto demo flow: match + approve + send invitation email ---
    try:
        _auto_invite_for_referral(
            conn,
            referral_id=result.referral.id,
            email_client=email_client,
        )
    except Exception:  # pragma: no cover - best-effort, never block referral creation
        logger.exception(
            "auto_invite.failed referral=%s — referral still created",
            result.referral.id,
        )

    return schemas.ReferralCreateResponse(
        resident=resident_to_response(result.resident),
        consent=consent_to_response(result.consent, scopes),
        referral=referral_to_response(result.referral),
    )


def _auto_invite_for_referral(
    conn: Connection,
    *,
    referral_id: str,
    email_client: EmailClient | None,
) -> None:
    """Run the deterministic matching workflow and dispatch invitations.

    Best-effort: silently skips when matching produces no candidates so
    the GP-side referral always succeeds even if the companion pool isn't
    seeded yet. Uses the existing MatchingWorkflowService — the same code
    path the operator dashboard's orchestrate + approve buttons drive.
    """
    workflow = MatchingWorkflowService(conn, email_client=email_client)
    try:
        plan = workflow.accept_referral_and_propose_matches(
            referral_id=referral_id,
            top_n_activities=10,
            top_n_groups=3,
            min_group_size=2,
            max_group_size=6,
            preferred_template_code="photography_walk",
        )
    except ValueError as exc:
        logger.info("auto_invite.no_match referral=%s reason=%s", referral_id, exc)
        return

    if not plan.top_activity_results or plan.grouping_result is None:
        logger.info(
            "auto_invite.skip referral=%s reason=no_candidates", referral_id
        )
        return
    grouping = plan.grouping_result
    if not grouping.groups:
        return

    from app.repositories import ActivityRepository, ReferralRepository
    from app.repositories.base import utc_now_iso
    from datetime import datetime, time as _time, timedelta, timezone

    referral = ReferralRepository(conn).get_referral(referral_id)
    referred_resident_id = referral.resident_id if referral else None

    top_group = next(
        (
            g
            for g in grouping.groups
            if any(m.id == referred_resident_id for m in g.members)
        ),
        grouping.groups[0],
    )
    if top_group.circle is None:
        return

    template = grouping.template
    activities_repo = ActivityRepository(conn)

    # Anchor the proposed circle to a fresh activity at the seeded Vondelpark
    # venue (the matcher's deterministic default). The operator can re-run
    # the LLM-driven orchestrate endpoint later for a richer venue.
    venue_row = conn.execute(
        "SELECT * FROM venues WHERE name = ? AND city = ? LIMIT 1",
        ("Vondelpark", "Amsterdam"),
    ).fetchone()
    if venue_row is None:
        venue = activities_repo.create_venue(
            name="Vondelpark",
            address="Vondelpark, 1071 AA Amsterdam",
            city="Amsterdam",
            lat=52.358,
            lng=4.8686,
        )
        venue_id = venue.id
    else:
        venue_id = venue_row["id"]

    host_row = conn.execute(
        "SELECT * FROM hosts WHERE full_name = ? LIMIT 1",
        ("Maya · CivicCircles host",),
    ).fetchone()
    if host_row is None:
        host = activities_repo.create_host(
            full_name="Maya · CivicCircles host",
            host_type="facilitator",
            contact_email="maya@civiccircles.demo",
        )
        host_id = host.id
    else:
        host_id = host_row["id"]

    now = datetime.now(timezone.utc)
    days_ahead = (5 - now.weekday()) % 7
    start_at = datetime.combine(
        (now + timedelta(days=days_ahead)).date(), _time(10, 30), tzinfo=timezone.utc
    )
    if start_at <= now:
        start_at = start_at + timedelta(days=7)
    end_at = start_at + timedelta(minutes=template.typical_duration_minutes)

    activity = activities_repo.create_activity(
        title=template.title,
        activity_type=template.code,
        venue_id=venue_id,
        host_id=host_id,
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        capacity=template.typical_group_size_max,
        risk_level=template.risk_level,
        approval_status="approved",  # auto-approve for demo
        cost_cents=0,
    )
    conn.execute(
        "UPDATE circles SET activity_id = ?, updated_at = ? WHERE id = ?",
        (activity.id, utc_now_iso(), top_group.circle.id),
    )

    # Safety net: the matcher's fair-grouping may have placed the referred
    # resident in a different group. Ensure they're in this circle so the
    # email actually goes to them.
    if referred_resident_id is not None:
        existing_member_ids = {
            m.resident_id
            for m in activities_repo.list_circle_members(circle_id=top_group.circle.id)
        }
        if referred_resident_id not in existing_member_ids:
            activities_repo.add_circle_member(
                circle_id=top_group.circle.id,
                resident_id=referred_resident_id,
            )
    conn.commit()

    workflow.send_invitations_for_approved_circle(
        circle_id=top_group.circle.id, actor_id="auto_demo"
    )


@router.get("/{referral_id}", response_model=schemas.ReferralResponse)
def get_referral(
    referral_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ReferralResponse:
    referral = ReferralRepository(conn).get_referral(referral_id)
    if referral is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    return referral_to_response(referral)


@router.patch("/{referral_id}/status", response_model=schemas.ReferralResponse)
def update_referral_status(
    referral_id: str,
    payload: schemas.ReferralStatusUpdateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ReferralResponse:
    repo = ReferralRepository(conn)
    if repo.get_referral(referral_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    repo.update_status(referral_id=referral_id, status=payload.status)
    conn.commit()
    updated = repo.get_referral(referral_id)
    assert updated is not None
    return referral_to_response(updated)
