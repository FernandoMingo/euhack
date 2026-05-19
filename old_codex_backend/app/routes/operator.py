from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.matching import explain_match, score_activity
from app.models import Activity, AuditItem, Circle, CircleMember, Feedback, Proposal, Resident
from app.routes.common import activity_circle, circle_members, feedback_for_residents, get_activity, proposal_payload

router = APIRouter(prefix="/api/operator", tags=["operator"])


def _proposal(session: Session, proposal_id: str) -> Proposal:
    proposal = session.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


def _circle_residents(session: Session, circle: Circle) -> list[Resident]:
    members = circle_members(session, circle.id)
    residents: list[Resident] = []
    for member in members:
        resident = session.get(Resident, member.resident_id)
        if resident:
            residents.append(resident)
    return residents


@router.get("/proposals")
def proposals(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(select(Proposal)).all()
    return [proposal_payload(session, proposal) for proposal in rows]


@router.get("/proposals/{proposal_id}")
def proposal_detail(proposal_id: str, session: Session = Depends(get_session)) -> dict:
    proposal = _proposal(session, proposal_id)
    return proposal_payload(session, proposal)


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, session: Session = Depends(get_session)) -> dict:
    proposal = _proposal(session, proposal_id)
    activity = get_activity(session, proposal.activity_id)
    proposal.status = "approved"
    proposal.human_approval_status = "approved"
    activity.status = "approved"
    session.add(proposal)
    session.add(activity)
    session.commit()
    session.refresh(proposal)
    return proposal_payload(session, proposal)


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, session: Session = Depends(get_session)) -> dict:
    proposal = _proposal(session, proposal_id)
    activity = get_activity(session, proposal.activity_id)
    proposal.status = "rejected"
    proposal.human_approval_status = "rejected"
    activity.status = "rejected"
    session.add(proposal)
    session.add(activity)
    session.commit()
    session.refresh(proposal)
    return proposal_payload(session, proposal)


@router.get("/matching-graph/{circle_id}")
def matching_graph(circle_id: str, session: Session = Depends(get_session)) -> dict:
    circle = session.get(Circle, circle_id)
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    members = session.exec(select(CircleMember).where(CircleMember.circle_id == circle_id)).all()
    nodes = [
        {
            "id": member.anonymous_label.lower().replace(" ", "_"),
            "label": member.anonymous_label,
            "kind": "resident",
        }
        for member in members
    ]
    nodes.append({"id": circle.activity_id, "label": "Calm Photography Walk", "kind": "activity"})
    edges = [
        {"from": node["id"], "to": circle.activity_id, "signals": circle.compatibility_signals[:4]}
        for node in nodes
        if node["kind"] == "resident"
    ]
    return {
        "circle_id": circle.id,
        "activity_id": circle.activity_id,
        "compatibility_signals": circle.compatibility_signals,
        "nodes": nodes,
        "edges": edges,
        "privacy_note": "Operator graph uses anonymous participant labels. No social value ranking.",
    }


@router.get("/audit/{activity_id}")
def audit(activity_id: str, session: Session = Depends(get_session)) -> dict:
    activity = get_activity(session, activity_id)
    rows = session.exec(select(AuditItem).where(AuditItem.activity_id == activity_id)).all()
    return {
        "activity_id": activity.id,
        "activity_title": activity.title,
        "items": [{"id": item.id, "label": item.label, "status": item.status, "detail": item.detail} for item in rows],
    }


@router.get("/rankings/{circle_id}")
def rankings(circle_id: str, session: Session = Depends(get_session)) -> dict:
    circle = session.get(Circle, circle_id)
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    residents = _circle_residents(session, circle)
    feedback = feedback_for_residents(session, residents)
    activities = session.exec(select(Activity)).all()
    ranked = sorted(
        [score_activity(activity, residents, feedback) for activity in activities],
        key=lambda item: item.score,
        reverse=True,
    )
    proposal = session.exec(select(Proposal).where(Proposal.activity_id == circle.activity_id)).first()
    return {
        "ranked_activities": [
            {
                "activity_id": item.activity.id,
                "title": item.activity.title,
                "score": item.score,
                "component_scores": item.component_scores,
                "hard_constraints_passed": item.hard_constraints_passed,
                "hard_constraints_failed": item.hard_constraints_failed,
                "reasons_ranked_lower": item.reasons_ranked_lower,
            }
            for item in ranked
        ],
        "explanation": explain_match(ranked, residents, proposal.human_approval_status if proposal else "pending_human_approval"),
    }
