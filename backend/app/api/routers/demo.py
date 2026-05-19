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
  - Resident inbox: invitations joined with activity + venue + host.
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

from app.api.deps import get_connection
from app.repositories import (
    ActivityRepository,
    ActivityTemplateRepository,
    MatchingRepository,
    ProfessionalRepository,
    ReferralRepository,
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


class _ResidentInboxOut(BaseModel):
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
) -> _ProposalOut:
    """One click: matching workflow → activity from top template → top circle anchored.

    Leaves the activity in `proposed` status. Operator still has to call
    /approve to flip it to `approved` and dispatch invitations.
    """
    repos = _repos(conn)

    preferred = payload.preferred_template_code if payload else "photography_walk"
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
    # If matching put Sofia in no group (it's fair-grouping; she may have
    # tied with others), fall back to the top group and append her below.
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
    venue_row = _vondelpark_venue(repos)
    host_row = _demo_host(repos)
    venue_id = venue_row.id if hasattr(venue_row, "id") else venue_row["id"]
    host_id = host_row.id if hasattr(host_row, "id") else host_row["id"]

    start_at = _next_saturday_10_30()
    end_at = start_at + timedelta(minutes=template.typical_duration_minutes)

    activity = repos.activities.create_activity(
        title=template.title,
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

    service = MatchingWorkflowService(conn)
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


@router.get("/residents/{resident_id}/inbox", response_model=_ResidentInboxOut)
def resident_inbox(
    resident_id: str,
    conn: Connection = Depends(get_connection),
) -> _ResidentInboxOut:
    repos = _repos(conn)
    resident = _resident_summary(repos, resident_id)

    rows = repos.conn.execute(
        """
        SELECT id, circle_id, activity_id, status FROM invitations
         WHERE resident_id = ?
         ORDER BY sent_at DESC
        """,
        (resident_id,),
    ).fetchall()

    invitations: list[_InvitationOut] = []
    for row in rows:
        try:
            proposal = _proposal_for_circle(repos, row["circle_id"])
        except HTTPException:
            continue
        invitations.append(
            _InvitationOut(
                id=row["id"],
                status=row["status"],
                activity_id=row["activity_id"],
                circle_id=row["circle_id"],
                activity=proposal.activity,
                template_code=proposal.template_code,
                fit_score=proposal.fit_score,
                members=proposal.members,
            )
        )
    return _ResidentInboxOut(resident=resident, invitations=invitations)


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
