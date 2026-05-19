"""
Demo orchestration router.

This is the thin compatibility + orchestration layer that the frontend
calls during the recorded demo. It wraps the lower-level primitives
(matching workflow, attendance, feedback, invitations) into the shapes
the UI wants:

  - Operator inbox: pending referrals + proposed circles awaiting decision.
  - One-click orchestrate: run matching for a referral, materialise an
    activity for the top-ranked template, anchor the top proposed circle
    to that activity. Operator still needs to click Approve.
  - Approve / reject: records operator decision, flips activity approval,
    sends invitations.
  - Resident inbox: thin alias of ``GET /api/residents/{id}/inbox`` (privacy-safe
    ``resident_inbox_items`` via ``InvitationInboxService`` / ``ResidentInboxRepository``).
  - Check-in + circle-reveal: arrival flips reveal from locked to unlocked.
  - Reflection: thin wrap of /api/activities/{id}/feedback.
  - GP dashboard: referrals + resident summaries.

Everything here is demo-shaped. It is NOT intended as the production
operator API surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from sqlite3 import Connection
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api import schemas
from app.api.converters import inbox_item_to_response
from app.api.deps import get_connection, get_email_client, get_llm_client
from app.services.email_client import EmailClient
from app.services.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMResponseError,
)
from app.services import ActivityPlanningService
from app.repositories import (
    ActivityRepository,
    ActivityTemplateRepository,
    MatchingRepository,
    ProfessionalRepository,
    ReferralRepository,
    ResidentInboxRepository,
    ResidentRepository,
)
from app.repositories.base import new_id, utc_now_iso
from app.services import MatchingWorkflowService

router = APIRouter(prefix="/api/demo", tags=["demo"])


# ---------------------------------------------------------------------------
# Response shapes (demo-specific; not promoted to schemas.py on purpose).
# ---------------------------------------------------------------------------


class _VenueOut(BaseModel):
    id: str
    name: str
    address: str
    city: str
    lat: float | None
    lng: float | None


class _HostOut(BaseModel):
    id: str
    full_name: str
    host_type: str


class _ActivityOut(BaseModel):
    id: str
    title: str
    activity_type: str
    start_at: datetime
    end_at: datetime
    capacity: int
    cost_cents: int
    risk_level: str
    approval_status: str
    venue: _VenueOut
    host: _HostOut | None


class _ResidentSummary(BaseModel):
    id: str
    first_name: str
    neighborhood: str | None
    social_comfort: str
    preferred_group_size_min: int
    preferred_group_size_max: int


class _ProfessionalSummary(BaseModel):
    id: str
    full_name: str
    role: str
    organization: str | None
    city: str | None
    verification_status: str


class _PendingReferralOut(BaseModel):
    referral_id: str
    referral_reason: str | None
    created_at: datetime
    resident: _ResidentSummary
    professional: _ProfessionalSummary
    consent_text_version: str = "v1.0-nl-2026-05"


class _ProposalOut(BaseModel):
    circle_id: str
    activity: _ActivityOut
    template_code: str
    template_title: str
    fit_score: float | None
    shared_interests: list[str]
    shared_availability: list[str]
    members: list[_ResidentSummary]
    summary_text: str
    consent_text_version: str = "v1.0-nl-2026-05"


class _OperatorInboxOut(BaseModel):
    pending_referrals: list[_PendingReferralOut]
    proposals: list[_ProposalOut]
    consent_text_version: str = "v1.0-nl-2026-05"


class _OrchestrateRequest(BaseModel):
    operator_id: str = Field(default="operator_demo")
    preferred_template_code: str | None = Field(
        default="photography_walk",
        description=(
            "Template code to prefer if it appears in the top-N ranking. "
            "Keeps the recorded demo on-narrative (Vondelpark photography walk). "
            "Set to null to use the raw ranker output."
        ),
    )
    use_llm: bool = Field(
        default=True,
        description=(
            "When true (default), after the ranker picks the top template the "
            "ActivityPlanningService is called so the LLM proposes the activity "
            "title, venue, duration and safety notes. Falls back to the "
            "template defaults if no LLM client is configured or the call fails."
        ),
    )


class _ApproveRequest(BaseModel):
    operator_id: str = Field(default="operator_demo")
    reason: str | None = None


class _InvitationOut(BaseModel):
    id: str
    status: str
    activity_id: str
    circle_id: str
    activity: _ActivityOut
    template_code: str | None
    fit_score: float | None
    members: list[_ResidentSummary]


class _ResidentInvitationsOut(BaseModel):
    """Rich resident-scoped view used by the demo map page.

    This is intentionally separate from the privacy-safe inbox at
    ``/api/demo/residents/{id}/inbox`` (which mirrors the canonical
    resident inbox). The map needs venue coordinates, circle members
    and activity timing, so we re-hydrate from the underlying tables
    for the resident who owns the invitations.
    """

    resident: _ResidentSummary
    invitations: list[_InvitationOut]


class _CheckInRequest(BaseModel):
    resident_id: str


class _RevealAttendeeOut(BaseModel):
    first_name: str
    common_ground: list[str]
    conversation_starter: str


class _CircleRevealOut(BaseModel):
    activity_id: str
    locked: bool
    attendees: list[_RevealAttendeeOut]


class _ReflectionRequest(BaseModel):
    resident_id: str
    felt_after: Literal["worse", "same", "better"] | None = "better"
    would_repeat: bool | None = True
    notes: str | None = None


class _ProfessionalDashboardOut(BaseModel):
    professional: _ProfessionalSummary
    referrals: list[_PendingReferralOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Repos:
    conn: Connection
    activities: ActivityRepository
    templates: ActivityTemplateRepository
    matching: MatchingRepository
    professionals: ProfessionalRepository
    referrals: ReferralRepository
    residents: ResidentRepository


def _repos(conn: Connection) -> _Repos:
    return _Repos(
        conn=conn,
        activities=ActivityRepository(conn),
        templates=ActivityTemplateRepository(conn),
        matching=MatchingRepository(conn),
        professionals=ProfessionalRepository(conn),
        referrals=ReferralRepository(conn),
        residents=ResidentRepository(conn),
    )


def _next_saturday_10_30(reference: datetime | None = None) -> datetime:
    """Next Saturday at 10:30 local time, as an aware UTC datetime.

    Used by the orchestrator to give the demo's photography walk a
    realistic start. If today is Saturday and it's before 10:30, today
    wins; otherwise the following Saturday.
    """
    now = reference or datetime.now(timezone.utc)
    days_ahead = (5 - now.weekday()) % 7  # 5 = Saturday
    candidate = (now + timedelta(days=days_ahead)).date()
    saturday = datetime.combine(candidate, time(10, 30), tzinfo=timezone.utc)
    if saturday <= now:
        saturday = saturday + timedelta(days=7)
    return saturday


def _vondelpark_venue(repos: _Repos) -> object:
    """Get-or-create the Vondelpark venue used in the demo narrative."""
    existing = repos.conn.execute(
        "SELECT id FROM venues WHERE name = ? AND city = ? LIMIT 1",
        ("Vondelpark", "Amsterdam"),
    ).fetchone()
    if existing is not None:
        venue = repos.activities.get_activity  # no-op to please type
        row = repos.conn.execute(
            "SELECT * FROM venues WHERE id = ?", (existing["id"],)
        ).fetchone()
        return row
    venue = repos.activities.create_venue(
        name="Vondelpark",
        address="Vondelpark, 1071 AA Amsterdam",
        city="Amsterdam",
        lat=52.358,
        lng=4.8686,
    )
    return venue


def _demo_host(repos: _Repos) -> object:
    existing = repos.conn.execute(
        "SELECT * FROM hosts WHERE full_name = ? LIMIT 1",
        ("Maya · CivicCircles host",),
    ).fetchone()
    if existing is not None:
        return existing
    return repos.activities.create_host(
        full_name="Maya · CivicCircles host",
        host_type="facilitator",
        contact_email="maya@civiccircles.demo",
    )


def _venue_to_out(row) -> _VenueOut:
    if hasattr(row, "id"):
        return _VenueOut(
            id=row.id,
            name=row.name,
            address=row.address,
            city=row.city,
            lat=row.lat,
            lng=row.lng,
        )
    return _VenueOut(
        id=row["id"],
        name=row["name"],
        address=row["address"],
        city=row["city"],
        lat=row["lat"],
        lng=row["lng"],
    )


def _host_to_out(row) -> _HostOut | None:
    if row is None:
        return None
    if hasattr(row, "id"):
        return _HostOut(id=row.id, full_name=row.full_name, host_type=row.host_type)
    return _HostOut(id=row["id"], full_name=row["full_name"], host_type=row["host_type"])


def _activity_to_out(repos: _Repos, activity_id: str) -> _ActivityOut:
    activity = repos.activities.get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail=f"Activity {activity_id} not found")
    venue_row = repos.conn.execute(
        "SELECT * FROM venues WHERE id = ?", (activity.venue_id,)
    ).fetchone()
    host_row = None
    if activity.host_id:
        host_row = repos.conn.execute(
            "SELECT * FROM hosts WHERE id = ?", (activity.host_id,)
        ).fetchone()
    return _ActivityOut(
        id=activity.id,
        title=activity.title,
        activity_type=activity.activity_type,
        start_at=activity.start_at,
        end_at=activity.end_at,
        capacity=activity.capacity,
        cost_cents=activity.cost_cents,
        risk_level=activity.risk_level,
        approval_status=activity.approval_status,
        venue=_venue_to_out(venue_row),
        host=_host_to_out(host_row),
    )


def _resident_summary(repos: _Repos, resident_id: str) -> _ResidentSummary:
    resident = repos.residents.get_resident(resident_id)
    if resident is None:
        raise HTTPException(status_code=404, detail=f"Resident {resident_id} not found")
    return _ResidentSummary(
        id=resident.id,
        first_name=resident.first_name,
        neighborhood=resident.neighborhood,
        social_comfort=resident.social_comfort,
        preferred_group_size_min=resident.preferred_group_size_min,
        preferred_group_size_max=resident.preferred_group_size_max,
    )


def _professional_summary(repos: _Repos, professional_id: str) -> _ProfessionalSummary:
    professional = repos.professionals.get_professional(professional_id)
    if professional is None:
        raise HTTPException(
            status_code=404, detail=f"Professional {professional_id} not found"
        )
    return _ProfessionalSummary(
        id=professional.id,
        full_name=professional.full_name,
        role=professional.role,
        organization=professional.organization,
        city=professional.city,
        verification_status=professional.verification_status,
    )


def _pending_referral_out(repos: _Repos, referral_id: str) -> _PendingReferralOut:
    referral = repos.referrals.get_referral(referral_id)
    if referral is None:
        raise HTTPException(status_code=404, detail=f"Referral {referral_id} not found")
    consent_row = repos.conn.execute(
        """
        SELECT consent_text_version FROM consent_records
         WHERE resident_id = ? AND professional_id = ?
         ORDER BY granted_at DESC LIMIT 1
        """,
        (referral.resident_id, referral.professional_id),
    ).fetchone()
    return _PendingReferralOut(
        referral_id=referral.id,
        referral_reason=referral.referral_reason,
        created_at=referral.created_at,
        resident=_resident_summary(repos, referral.resident_id),
        professional=_professional_summary(repos, referral.professional_id),
        consent_text_version=(
            consent_row["consent_text_version"]
            if consent_row is not None
            else "v1.0-nl-2026-05"
        ),
    )


def _conversation_starter(template_code: str, shared_interests: list[str]) -> str:
    if shared_interests:
        return f"Ask about their favourite {shared_interests[0]} spot."
    starters = {
        "photography_walk": "Ask what they like to take photos of.",
        "slow_park_walk": "Ask what their favourite quiet corner of the park is.",
        "picnic_in_the_park": "Ask what they brought to share.",
    }
    return starters.get(template_code, "Ask what brought them today.")


def _proposal_for_circle(repos: _Repos, circle_id: str) -> _ProposalOut:
    circle = repos.activities.get_circle(circle_id)
    if circle is None:
        raise HTTPException(status_code=404, detail=f"Circle {circle_id} not found")
    if circle.activity_id is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Circle is not anchored to an activity yet; "
                "run /api/demo/operator/referrals/{id}/orchestrate first"
            ),
        )
    activity_out = _activity_to_out(repos, circle.activity_id)

    template_code = ""
    template_title = ""
    if circle.template_id:
        row = repos.conn.execute(
            "SELECT code, title FROM activity_templates WHERE id = ?",
            (circle.template_id,),
        ).fetchone()
        if row is not None:
            template_code = row["code"]
            template_title = row["title"]

    member_rows = repos.activities.list_circle_members(circle_id=circle_id)
    members = [_resident_summary(repos, m.resident_id) for m in member_rows]

    import json

    shared = {"shared_interests": [], "shared_availability": []}
    try:
        parsed = json.loads(circle.shared_signals_json or "{}")
        if isinstance(parsed, dict):
            shared["shared_interests"] = list(parsed.get("shared_interests") or [])
            shared["shared_availability"] = list(parsed.get("shared_availability") or [])
    except json.JSONDecodeError:
        pass

    summary = (
        f"AI proposes {template_title or activity_out.title} for {len(members)} residents "
        f"on {activity_out.start_at.strftime('%A %H:%M')} at {activity_out.venue.name}."
    )

    return _ProposalOut(
        circle_id=circle.id,
        activity=activity_out,
        template_code=template_code,
        template_title=template_title,
        fit_score=circle.fit_score,
        shared_interests=shared["shared_interests"],
        shared_availability=shared["shared_availability"],
        members=members,
        summary_text=summary,
    )


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


@router.get("/operator/inbox", response_model=_OperatorInboxOut)
def operator_inbox(
    conn: Connection = Depends(get_connection),
) -> _OperatorInboxOut:
    repos = _repos(conn)

    pending_rows = repos.conn.execute(
        """
        SELECT id FROM referrals
         WHERE status = 'submitted'
         ORDER BY created_at DESC
         LIMIT 25
        """
    ).fetchall()
    pending = [_pending_referral_out(repos, row["id"]) for row in pending_rows]

    circles = repos.activities.list_circles(status="proposed", limit=25)
    proposals: list[_ProposalOut] = []
    for circle in circles:
        if circle.activity_id is None:
            continue
        try:
            proposals.append(_proposal_for_circle(repos, circle.id))
        except HTTPException:
            continue

    return _OperatorInboxOut(pending_referrals=pending, proposals=proposals)


@router.post(
    "/operator/referrals/{referral_id}/orchestrate",
    response_model=_ProposalOut,
)
def orchestrate_referral(
    referral_id: str,
    payload: _OrchestrateRequest | None = Body(default=None),
    conn: Connection = Depends(get_connection),
    llm_client: LLMClient | None = Depends(get_llm_client),
) -> _ProposalOut:
    """One click: matching workflow → activity from top template → top circle anchored.

    When ``use_llm`` is true and an ``LLMClient`` is configured, the activity
    title / duration / venue are taken from a GPT-generated plan instead of
    the template defaults. Falls back to the deterministic template path on
    any LLM error.

    Leaves the activity in `proposed` status. Operator still has to call
    /approve to flip it to `approved` and dispatch invitations.
    """
    repos = _repos(conn)

    preferred = payload.preferred_template_code if payload else "photography_walk"
    use_llm = payload.use_llm if payload else True
    service = MatchingWorkflowService(conn)
    try:
        workflow = service.accept_referral_and_propose_matches(
            referral_id=referral_id,
            top_n_activities=10,
            top_n_groups=3,
            min_group_size=2,
            max_group_size=6,
            preferred_template_code=preferred,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not workflow.top_activity_results:
        raise HTTPException(
            status_code=422,
            detail="Matching produced no activity candidates; check the resident profile.",
        )
    grouping = workflow.grouping_result
    if grouping is None or not grouping.groups:
        raise HTTPException(
            status_code=422,
            detail="No proposed circles for this referral. Need more residents in the pool.",
        )

    referral = repos.referrals.get_referral(referral_id)
    referred_resident_id = referral.resident_id if referral else None

    # Prefer the top group that actually contains the referred resident.
    # If matching put the resident in no group, fall back to the top group
    # and append them below.
    top_group = next(
        (
            g
            for g in grouping.groups
            if any(m.id == referred_resident_id for m in g.members)
        ),
        grouping.groups[0],
    )
    if top_group.circle is None:
        raise HTTPException(
            status_code=500,
            detail="Matching engine did not persist the top circle.",
        )

    template = grouping.template

    # ---- LLM activity planning (optional, falls back on any failure) ----
    llm_title: str | None = None
    llm_duration: int | None = None
    llm_venue_name: str | None = None
    llm_venue_address: str | None = None
    llm_used = False
    if use_llm and llm_client is not None:
        try:
            planner = ActivityPlanningService(conn, llm_client=llm_client)
            plan_result = planner.generate_plan_for_circle(
                circle_id=top_group.circle.id,
                operator_constraints={
                    "activity_type": f"calm small-group {template.title.lower()}",
                    "search_area": "Amsterdam Oud-West / Vondelpark area",
                    "budget": "free or low cost",
                    "preferred_time_window": "Saturday morning",
                    "venue_requirements": [
                        "small-group friendly",
                        "step-free, reachable by public transport",
                        "no alcohol involved",
                    ],
                },
                requested_by=(payload.operator_id if payload else "operator_demo"),
            )
            content = plan_result.response_content or {}
            if isinstance(content, dict):
                llm_title = content.get("title") or content.get("activity_title")
                duration = content.get("duration_minutes")
                if isinstance(duration, int) and 15 <= duration <= 480:
                    llm_duration = duration
                venue_research = content.get("venue_research") or {}
                if isinstance(venue_research, dict):
                    llm_venue_name = venue_research.get("selected_venue_name")
                    llm_venue_address = venue_research.get("selected_venue_address")
            llm_used = True
        except (LLMConfigurationError, LLMResponseError, ValueError):
            # LLM unavailable or malformed response: fall back to deterministic
            # path silently. The plan failure is already audit-logged by the
            # ActivityPlanningService.
            llm_used = False

    # ---- Venue: prefer LLM suggestion, else seeded Vondelpark default ----
    if llm_venue_name and llm_venue_address:
        existing_venue = repos.conn.execute(
            "SELECT * FROM venues WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (llm_venue_name,),
        ).fetchone()
        if existing_venue is not None:
            venue_row = existing_venue
        else:
            venue_row = repos.activities.create_venue(
                name=llm_venue_name,
                address=llm_venue_address,
                city="Amsterdam",
                lat=52.358,
                lng=4.8686,
            )
    else:
        venue_row = _vondelpark_venue(repos)

    host_row = _demo_host(repos)
    venue_id = venue_row.id if hasattr(venue_row, "id") else venue_row["id"]
    host_id = host_row.id if hasattr(host_row, "id") else host_row["id"]

    start_at = _next_saturday_10_30()
    duration_minutes = llm_duration or template.typical_duration_minutes
    end_at = start_at + timedelta(minutes=duration_minutes)

    activity_title = llm_title or template.title
    activity = repos.activities.create_activity(
        title=activity_title,
        activity_type=template.code,
        venue_id=venue_id,
        host_id=host_id,
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        capacity=template.typical_group_size_max,
        risk_level=template.risk_level,
        approval_status="proposed",
        cost_cents=0,
    )

    repos.conn.execute(
        "UPDATE circles SET activity_id = ?, updated_at = ? WHERE id = ?",
        (activity.id, utc_now_iso(), top_group.circle.id),
    )

    # Safety net: if the referred resident is not yet a member of the chosen
    # circle, add her. The demo can't tell Sofia's story without Sofia in it.
    if referred_resident_id is not None:
        existing_member_ids = {
            m.resident_id
            for m in repos.activities.list_circle_members(circle_id=top_group.circle.id)
        }
        if referred_resident_id not in existing_member_ids:
            repos.activities.add_circle_member(
                circle_id=top_group.circle.id,
                resident_id=referred_resident_id,
            )

    repos.conn.commit()

    return _proposal_for_circle(repos, top_group.circle.id)


@router.post(
    "/operator/circles/{circle_id}/approve",
    response_model=list[_InvitationOut],
)
def approve_proposal(
    circle_id: str,
    payload: _ApproveRequest | None = Body(default=None),
    conn: Connection = Depends(get_connection),
    email_client: EmailClient | None = Depends(get_email_client),
) -> list[_InvitationOut]:
    """Approve the proposal: flip activity to approved, record decision, send invitations."""
    repos = _repos(conn)
    operator_id = (payload.operator_id if payload else None) or "operator_demo"
    reason = payload.reason if payload else None

    circle = repos.activities.get_circle(circle_id)
    if circle is None:
        raise HTTPException(status_code=404, detail=f"Circle {circle_id} not found")
    if circle.activity_id is None:
        raise HTTPException(status_code=409, detail="Circle is not anchored to an activity")

    repos.conn.execute(
        "UPDATE activities SET approval_status = 'approved', updated_at = ? WHERE id = ?",
        (utc_now_iso(), circle.activity_id),
    )
    repos.conn.commit()

    service = MatchingWorkflowService(conn, email_client=email_client)
    service.record_operator_decision(
        activity_id=circle.activity_id,
        operator_id=operator_id,
        decision="approved",
        reason=reason,
    )
    try:
        invitations = service.send_invitations_for_approved_circle(
            circle_id=circle_id, actor_id=operator_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    out: list[_InvitationOut] = []
    proposal = _proposal_for_circle(repos, circle_id)
    for inv in invitations:
        out.append(
            _InvitationOut(
                id=inv.id,
                status=inv.status,
                activity_id=inv.activity_id,
                circle_id=inv.circle_id,
                activity=proposal.activity,
                template_code=proposal.template_code,
                fit_score=proposal.fit_score,
                members=proposal.members,
            )
        )
    return out


@router.post(
    "/operator/circles/{circle_id}/reject",
    response_model=_ProposalOut,
)
def reject_proposal(
    circle_id: str,
    payload: _ApproveRequest | None = Body(default=None),
    conn: Connection = Depends(get_connection),
) -> _ProposalOut:
    repos = _repos(conn)
    operator_id = (payload.operator_id if payload else None) or "operator_demo"
    reason = payload.reason if payload else None

    circle = repos.activities.get_circle(circle_id)
    if circle is None:
        raise HTTPException(status_code=404, detail=f"Circle {circle_id} not found")
    if circle.activity_id is None:
        raise HTTPException(status_code=409, detail="Circle is not anchored to an activity")

    repos.conn.execute(
        "UPDATE activities SET approval_status = 'rejected', updated_at = ? WHERE id = ?",
        (utc_now_iso(), circle.activity_id),
    )
    repos.activities.update_circle_status(circle_id=circle_id, status="cancelled")
    repos.conn.commit()

    service = MatchingWorkflowService(conn)
    service.record_operator_decision(
        activity_id=circle.activity_id,
        operator_id=operator_id,
        decision="rejected",
        reason=reason,
    )
    return _proposal_for_circle(repos, circle_id)


# ---------------------------------------------------------------------------
# Resident
# ---------------------------------------------------------------------------


@router.get(
    "/residents/{resident_id}/inbox",
    response_model=list[schemas.ResidentInboxItemResponse],
)
def resident_inbox(
    resident_id: str,
    status_filter: schemas.InboxItemStatusLiteral | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_connection),
) -> list[schemas.ResidentInboxItemResponse]:
    """Privacy-safe resident inbox (same data as ``/api/residents/{id}/inbox``)."""
    if ResidentRepository(conn).get_resident(resident_id) is None:
        raise HTTPException(status_code=404, detail="Resident not found")
    items = ResidentInboxRepository(conn).list_for_resident(
        resident_id=resident_id, status=status_filter, limit=limit
    )
    return [inbox_item_to_response(item) for item in items]


@router.get(
    "/residents/{resident_id}/invitations",
    response_model=_ResidentInvitationsOut,
)
def resident_invitations(
    resident_id: str,
    conn: Connection = Depends(get_connection),
) -> _ResidentInvitationsOut:
    """Rich, resident-scoped invitation view for the demo map page.

    Returns only invitations whose ``resident_id`` matches the path param,
    so the caller can never see other residents' invitations even if they
    forge another id in the localStorage session.
    """
    repos = _repos(conn)
    if repos.residents.get_resident(resident_id) is None:
        raise HTTPException(status_code=404, detail="Resident not found")

    rows = repos.conn.execute(
        """
        SELECT i.id AS invitation_id, i.status, i.activity_id, i.circle_id
          FROM invitations i
          JOIN activities a ON a.id = i.activity_id
         WHERE i.resident_id = ?
           AND a.approval_status IN ('approved', 'proposed')
         ORDER BY a.start_at ASC
        """,
        (resident_id,),
    ).fetchall()

    invitations: list[_InvitationOut] = []
    for row in rows:
        circle = repos.activities.get_circle(row["circle_id"])
        template_code: str | None = None
        fit_score: float | None = None
        members: list[_ResidentSummary] = []
        if circle is not None:
            fit_score = circle.fit_score
            if circle.template_id:
                trow = repos.conn.execute(
                    "SELECT code FROM activity_templates WHERE id = ?",
                    (circle.template_id,),
                ).fetchone()
                if trow is not None:
                    template_code = trow["code"]
            member_rows = repos.activities.list_circle_members(circle_id=circle.id)
            members = [_resident_summary(repos, m.resident_id) for m in member_rows]

        invitations.append(
            _InvitationOut(
                id=row["invitation_id"],
                status=row["status"],
                activity_id=row["activity_id"],
                circle_id=row["circle_id"],
                activity=_activity_to_out(repos, row["activity_id"]),
                template_code=template_code,
                fit_score=fit_score,
                members=members,
            )
        )

    return _ResidentInvitationsOut(
        resident=_resident_summary(repos, resident_id),
        invitations=invitations,
    )


@router.post("/activities/{activity_id}/check-in")
def check_in(
    activity_id: str,
    payload: _CheckInRequest,
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    repos = _repos(conn)
    if repos.activities.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    repos.activities.record_attendance(
        activity_id=activity_id,
        resident_id=payload.resident_id,
        attendance_status="attended",
        check_in_at=utc_now_iso(),
    )
    repos.conn.commit()
    return {"checked_in": True, "activity_id": activity_id, "resident_id": payload.resident_id}


@router.get(
    "/activities/{activity_id}/circle-reveal",
    response_model=_CircleRevealOut,
)
def circle_reveal(
    activity_id: str,
    resident_id: str = Query(...),
    conn: Connection = Depends(get_connection),
) -> _CircleRevealOut:
    repos = _repos(conn)
    if repos.activities.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    checked_in = repos.conn.execute(
        """
        SELECT 1 FROM attendance_events
         WHERE activity_id = ? AND resident_id = ?
           AND attendance_status = 'attended'
           AND check_in_at IS NOT NULL
        """,
        (activity_id, resident_id),
    ).fetchone()

    if checked_in is None:
        return _CircleRevealOut(activity_id=activity_id, locked=True, attendees=[])

    circle_row = repos.conn.execute(
        """
        SELECT c.* FROM circles c
         JOIN circle_members m ON m.circle_id = c.id
         WHERE c.activity_id = ? AND m.resident_id = ?
         LIMIT 1
        """,
        (activity_id, resident_id),
    ).fetchone()
    if circle_row is None:
        return _CircleRevealOut(activity_id=activity_id, locked=False, attendees=[])

    import json

    shared_interests: list[str] = []
    try:
        parsed = json.loads(circle_row["shared_signals_json"] or "{}")
        if isinstance(parsed, dict):
            shared_interests = list(parsed.get("shared_interests") or [])
    except json.JSONDecodeError:
        pass

    template_code = ""
    if circle_row["template_id"]:
        trow = repos.conn.execute(
            "SELECT code FROM activity_templates WHERE id = ?",
            (circle_row["template_id"],),
        ).fetchone()
        template_code = trow["code"] if trow else ""

    member_rows = repos.activities.list_circle_members(circle_id=circle_row["id"])
    attendees: list[_RevealAttendeeOut] = []
    for member in member_rows:
        if member.resident_id == resident_id:
            continue
        summary = _resident_summary(repos, member.resident_id)
        attendees.append(
            _RevealAttendeeOut(
                first_name=summary.first_name,
                common_ground=shared_interests[:3],
                conversation_starter=_conversation_starter(template_code, shared_interests),
            )
        )

    return _CircleRevealOut(activity_id=activity_id, locked=False, attendees=attendees)


@router.post("/activities/{activity_id}/reflection")
def submit_reflection(
    activity_id: str,
    payload: _ReflectionRequest,
    conn: Connection = Depends(get_connection),
) -> dict[str, object]:
    repos = _repos(conn)
    if repos.activities.get_activity(activity_id) is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    feedback = repos.activities.add_feedback(
        activity_id=activity_id,
        resident_id=payload.resident_id,
        felt_after=payload.felt_after,
        activity_fit=None,
        group_comfort=None,
        would_repeat=payload.would_repeat,
        safety_reported=False,
        notes=payload.notes,
    )
    repos.conn.commit()
    return {
        "saved": True,
        "feedback_id": feedback.id,
        "activity_id": activity_id,
        "resident_id": payload.resident_id,
    }


# ---------------------------------------------------------------------------
# Professional dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/professionals/{professional_id}/dashboard",
    response_model=_ProfessionalDashboardOut,
)
def professional_dashboard(
    professional_id: str,
    conn: Connection = Depends(get_connection),
) -> _ProfessionalDashboardOut:
    repos = _repos(conn)
    professional = _professional_summary(repos, professional_id)
    referrals = repos.referrals.list_for_professional(professional_id)
    out_referrals = [_pending_referral_out(repos, r.id) for r in referrals]
    return _ProfessionalDashboardOut(professional=professional, referrals=out_referrals)


# ---------------------------------------------------------------------------
# Nearby activity seeding (browser geolocation -> activities around the user)
# ---------------------------------------------------------------------------


class _NearbyActivitiesRequest(BaseModel):
    lat: float = Field(..., description="Resident's current latitude.")
    lng: float = Field(..., description="Resident's current longitude.")
    count: int = Field(
        default=4,
        ge=1,
        le=8,
        description="How many nearby activities to materialise (1–8).",
    )


# Small lat/lng offsets in different bearings so the seeded activities sit
# in a believable ring around the resident, not stacked on the same pin.
# Each tuple is (dlat, dlng, label_suffix). Mid-latitude approximations:
#   ~0.0045 deg lat  ≈ 500m
#   ~0.0065 deg lng  ≈ 500m (at ~52°N)
_NEARBY_OFFSETS: tuple[tuple[float, float, str], ...] = (
    (0.0045, 0.0000, "north"),
    (-0.0045, 0.0000, "south"),
    (0.0000, 0.0065, "east"),
    (0.0000, -0.0065, "west"),
    (0.0030, 0.0045, "north-east"),
    (-0.0030, 0.0045, "south-east"),
    (0.0030, -0.0045, "north-west"),
    (-0.0030, -0.0045, "south-west"),
)


_NEARBY_TEMPLATE_PICKS: tuple[tuple[str, str, str], ...] = (
    ("photography_walk", "Photography Walk near you", "walk"),
    ("slow_park_walk", "Slow Park Walk near you", "walk"),
    ("museum_visit", "Quiet Museum Morning near you", "museum"),
    ("coffee_meetup", "Coffee meet-up near you", "coffee"),
    ("nature_walk_forest", "Easy Nature Walk near you", "walk"),
    ("library_event", "Library afternoon near you", "library"),
)


@router.post(
    "/residents/{resident_id}/nearby-activities",
    response_model=_ResidentInvitationsOut,
)
def seed_nearby_activities(
    resident_id: str,
    payload: _NearbyActivitiesRequest,
    conn: Connection = Depends(get_connection),
    email_client: EmailClient | None = Depends(get_email_client),
) -> _ResidentInvitationsOut:
    """Create N activities at small offsets around the resident's coordinates.

    Each activity gets its own venue (lat/lng = resident lat/lng + offset),
    a fresh circle containing the resident + up to four existing companions
    (any other residents in the DB), an ``invitations`` row addressed to
    the resident, and an inbox item + outbound email via the existing
    ``InvitationInboxService`` pipeline. Idempotent on re-call: rows for
    a given (resident_id, offset_slug) tuple are reused.
    """
    from datetime import timedelta as _td

    from app.dataclasses import Invitation
    from app.repositories.base import parse_dt
    from app.services import InvitationInboxService

    repos = _repos(conn)
    if repos.residents.get_resident(resident_id) is None:
        raise HTTPException(status_code=404, detail="Resident not found")

    # Pool of potential companions = every other active resident.
    pool_rows = conn.execute(
        "SELECT id FROM residents WHERE id != ? AND status='active' LIMIT 50",
        (resident_id,),
    ).fetchall()
    pool_ids = [row["id"] for row in pool_rows]
    if not pool_ids:
        raise HTTPException(
            status_code=422,
            detail="No companion residents in the pool. Run seed_jose_demo.py first.",
        )

    host_row = _demo_host(repos)
    host_id = host_row.id if hasattr(host_row, "id") else host_row["id"]

    count = min(payload.count, len(_NEARBY_OFFSETS), len(_NEARBY_TEMPLATE_PICKS))
    base_start = _next_saturday_10_30()

    inbox_service = InvitationInboxService(conn, email_client=email_client)

    for index in range(count):
        dlat, dlng, suffix = _NEARBY_OFFSETS[index]
        template_code, title_base, atype = _NEARBY_TEMPLATE_PICKS[index]
        venue_lat = round(payload.lat + dlat, 6)
        venue_lng = round(payload.lng + dlng, 6)

        # Deterministic IDs so re-calls patch rather than duplicate.
        slug = f"{resident_id}-{template_code}-{suffix}"
        activity_id = f"act-near-{slug}"
        venue_id = f"venue-near-{slug}"
        circle_id = f"circle-near-{slug}"
        invitation_id = f"inv-near-{slug}"

        # Venue (positioned at the resident's offset)
        conn.execute(
            """INSERT OR REPLACE INTO venues
               (id, name, address, city, lat, lng, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                venue_id,
                f"{title_base} · meet point",
                "Around you",
                "Local",
                venue_lat,
                venue_lng,
                utc_now_iso(),
                utc_now_iso(),
            ),
        )

        # Activity
        start_at = base_start + timedelta(days=index)
        end_at = start_at + timedelta(minutes=90)
        conn.execute(
            """INSERT OR REPLACE INTO activities
               (id, title, activity_type, venue_id, host_id, start_at, end_at,
                capacity, cost_cents, risk_level, approval_status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                activity_id,
                title_base,
                atype,
                venue_id,
                host_id,
                start_at.isoformat(),
                end_at.isoformat(),
                5,
                0,
                "low",
                "approved",
                utc_now_iso(),
                utc_now_iso(),
            ),
        )

        # Circle
        # Look up the template id from code; fall back to None if missing.
        trow = conn.execute(
            "SELECT id FROM activity_templates WHERE code = ? LIMIT 1",
            (template_code,),
        ).fetchone()
        template_pk = trow["id"] if trow is not None else None
        conn.execute(
            """INSERT OR REPLACE INTO circles
               (id, template_id, activity_id, status, fit_score,
                shared_signals_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                circle_id,
                template_pk,
                activity_id,
                "invitations_sent",
                0.86,
                "{\"shared_interests\":[\"around you\"]}",
                utc_now_iso(),
                utc_now_iso(),
            ),
        )

        # Members: resident + first 4 companions from the pool, rotating
        # so different circles don't all look identical.
        member_ids = [resident_id] + [
            pool_ids[(index + i) % len(pool_ids)] for i in range(min(4, len(pool_ids)))
        ]
        # Ensure no duplicates from the rotation overlapping resident_id
        seen: set[str] = set()
        unique_members = [m for m in member_ids if not (m in seen or seen.add(m))]
        # Wipe any prior membership of this circle so re-runs are clean.
        conn.execute("DELETE FROM circle_members WHERE circle_id = ?", (circle_id,))
        for mid in unique_members:
            conn.execute(
                """INSERT OR IGNORE INTO circle_members
                   (id, circle_id, resident_id, joined_at) VALUES (?,?,?,?)""",
                (new_id("circle_member"), circle_id, mid, utc_now_iso()),
            )

        # Invitation row addressed to the calling resident
        conn.execute(
            """INSERT OR REPLACE INTO invitations
               (id, circle_id, activity_id, resident_id, status,
                companion_pass_used, sent_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                invitation_id,
                circle_id,
                activity_id,
                resident_id,
                "sent",
                0,
                utc_now_iso(),
            ),
        )

    conn.commit()

    # Backfill inbox items + outbound emails for any nearby invitation
    # that doesn't already have one (idempotent).
    nearby_invitations = conn.execute(
        """
        SELECT * FROM invitations
         WHERE resident_id = ? AND id LIKE 'inv-near-%'
        """,
        (resident_id,),
    ).fetchall()
    for row in nearby_invitations:
        existing = conn.execute(
            "SELECT 1 FROM resident_inbox_items WHERE invitation_id = ?",
            (row["id"],),
        ).fetchone()
        if existing:
            continue
        invitation_obj = Invitation(
            id=row["id"],
            circle_id=row["circle_id"],
            activity_id=row["activity_id"],
            resident_id=row["resident_id"],
            status=row["status"],
            companion_pass_used=bool(row["companion_pass_used"]),
            sent_at=parse_dt(row["sent_at"]),  # type: ignore[arg-type]
            responded_at=parse_dt(row["responded_at"]) if row["responded_at"] else None,
        )
        inbox_service.create_artifacts_for_invitation(invitation=invitation_obj)
    conn.commit()

    # Re-use the existing /invitations endpoint serializer so the response
    # matches what the map page already renders.
    return resident_invitations(resident_id=resident_id, conn=conn)
