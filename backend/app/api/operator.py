from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.api.common import now_utc
from app.core.auth import Actor, require_role
from app.core.response import ok_response
from app.db import get_session
from app.models import Activity, Circle, ConsentRecord, Feedback, Invitation, Resident
from app.schemas import ProposalDecisionIn, ProposalPatchIn
from app.services.audit import build_audit_payload

router = APIRouter(prefix="/api/operator", tags=["operator"])


@router.get("/proposals")
def list_proposals(
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activities = session.exec(select(Activity)).all()
    return ok_response([a.model_dump() for a in activities], request)


@router.get("/proposals/{proposal_id}")
def proposal_detail(
    proposal_id: str,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activity = session.get(Activity, proposal_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ok_response(activity.model_dump(), request)


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(
    proposal_id: str,
    payload: ProposalDecisionIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activity = session.get(Activity, proposal_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Proposal not found")
    activity.approval_status = "approved"
    activity.lifecycle_status = "approved"
    activity.proposal_reason_code = payload.reason_code
    activity.updated_at = now_utc()
    session.add(activity)
    circles = session.exec(select(Circle).where(Circle.activity_id == proposal_id)).all()
    for circle in circles:
        circle.status = "invitations_sent"
        session.add(circle)
        for resident_id in circle.participant_ids:
            invitation = Invitation(
                id=f"invite_{proposal_id}_{resident_id}",
                resident_id=resident_id,
                activity_id=proposal_id,
                status="sent",
            )
            session.merge(invitation)
    session.commit()
    return ok_response(
        {"proposal_id": proposal_id, "approval_status": activity.approval_status, "reason_code": payload.reason_code},
        request,
    )


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: str,
    payload: ProposalDecisionIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activity = session.get(Activity, proposal_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Proposal not found")
    activity.approval_status = "rejected"
    activity.lifecycle_status = "rejected"
    activity.proposal_reason_code = payload.reason_code
    activity.updated_at = now_utc()
    session.add(activity)
    session.commit()
    return ok_response(
        {"proposal_id": proposal_id, "approval_status": activity.approval_status, "reason_code": payload.reason_code},
        request,
    )


@router.patch("/proposals/{proposal_id}")
def patch_proposal(
    proposal_id: str,
    payload: ProposalPatchIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activity = session.get(Activity, proposal_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if payload.start_time:
        activity.start_time = datetime.fromisoformat(payload.start_time)
    if payload.capacity:
        activity.capacity = payload.capacity
    if payload.location_name:
        location = dict(activity.location)
        location["name"] = payload.location_name
        activity.location = location
    activity.proposal_reason_code = payload.reason_code
    activity.updated_at = now_utc()
    session.add(activity)
    session.commit()
    return ok_response(activity.model_dump(), request)


@router.get("/matching-graph/{circle_id}")
def matching_graph(
    circle_id: str,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    circle = session.get(Circle, circle_id)
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    nodes = [{"id": rid, "type": "resident"} for rid in circle.participant_ids]
    nodes.append({"id": circle.activity_id, "type": "activity"})
    edges = [{"from": rid, "to": circle.activity_id, "label": "fit"} for rid in circle.participant_ids]
    return ok_response({"circle_id": circle.id, "nodes": nodes, "edges": edges}, request)


@router.get("/audit/{activity_id}")
def activity_audit(
    activity_id: str,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activity = session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    circle = session.exec(select(Circle).where(Circle.activity_id == activity_id)).first()
    participant_ids = circle.participant_ids if circle else []
    consents = session.exec(select(ConsentRecord).where(ConsentRecord.resident_id.in_(participant_ids))).all()
    payload = build_audit_payload(activity=activity, circle=circle, consent_records=consents)
    return ok_response(payload, request)


@router.get("/equity")
def equity_snapshot(
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    activities = session.exec(select(Activity)).all()
    residents = session.exec(select(Resident)).all()
    feedback = session.exec(select(Feedback)).all()
    free_pct = 0.0
    if activities:
        free_count = sum(1 for a in activities if a.cost == 0)
        free_pct = round((free_count / len(activities)) * 100, 1)
    step_free_pct = 0.0
    if activities:
        step_free_count = sum(1 for a in activities if "step_free_route" in a.accessibility)
        step_free_pct = round((step_free_count / len(activities)) * 100, 1)
    avg_radius = round(sum(r.location_radius_km for r in residents) / max(1, len(residents)), 1)
    felt_better_pct = 0.0
    if feedback:
        better = sum(1 for item in feedback if item.felt_after == "better")
        felt_better_pct = round((better / len(feedback)) * 100, 1)
    payload = {
        "free_activities_pct": free_pct,
        "step_free_activities_pct": step_free_pct,
        "average_resident_radius_km": avg_radius,
        "feedback_felt_better_pct": felt_better_pct,
        "neighborhood_coverage": "balanced",
    }
    return ok_response(payload, request)
