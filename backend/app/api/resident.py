from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.api.common import deterministic_or_random, now_utc
from app.core.auth import Actor, require_role
from app.core.response import ok_response
from app.db import get_session
from app.models import Circle, ConnectionRequest, Feedback, Invitation, Resident
from app.schemas import CompanionPassIn, ConnectionRequestIn, FeedbackIn

router = APIRouter(prefix="/api", tags=["resident"])


def _resident_from_actor(session: Session, actor: Actor) -> Resident:
    resident = session.get(Resident, actor.actor_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    return resident


@router.get("/resident/me")
def resident_me(
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    resident = _resident_from_actor(session, actor)
    return ok_response(resident.model_dump(), request)


@router.get("/resident/invitations")
def resident_invitations(
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    invitations = session.exec(select(Invitation).where(Invitation.resident_id == actor.actor_id)).all()
    return ok_response([inv.model_dump() for inv in invitations], request)


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(
    invitation_id: str,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    invitation = session.get(Invitation, invitation_id)
    if not invitation or invitation.resident_id != actor.actor_id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "accepted"
    invitation.accepted_at = now_utc()
    session.add(invitation)
    session.commit()
    return ok_response({"invitation_id": invitation.id, "status": invitation.status}, request)


@router.post("/invitations/{invitation_id}/decline")
def decline_invitation(
    invitation_id: str,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    invitation = session.get(Invitation, invitation_id)
    if not invitation or invitation.resident_id != actor.actor_id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "declined"
    invitation.declined_at = now_utc()
    session.add(invitation)
    session.commit()
    return ok_response({"invitation_id": invitation.id, "status": invitation.status}, request)


@router.post("/invitations/{invitation_id}/companion-pass")
def use_companion_pass(
    invitation_id: str,
    payload: CompanionPassIn,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    invitation = session.get(Invitation, invitation_id)
    if not invitation or invitation.resident_id != actor.actor_id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.companion_pass_used = True
    invitation.companion_guest_name = payload.guest_name
    session.add(invitation)
    session.commit()
    return ok_response(
        {"invitation_id": invitation.id, "companion_pass_used": invitation.companion_pass_used},
        request,
    )


@router.post("/activities/{activity_id}/check-in")
def check_in_activity(
    activity_id: str,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    resident = _resident_from_actor(session, actor)
    checked_in_ids = set(resident.checked_in_activity_ids)
    checked_in_ids.add(activity_id)
    resident.checked_in_activity_ids = sorted(checked_in_ids)
    resident.updated_at = now_utc()
    session.add(resident)
    session.commit()
    return ok_response({"resident_id": resident.id, "activity_id": activity_id, "checked_in": True}, request)


@router.get("/activities/{activity_id}/circle-reveal")
def circle_reveal(
    activity_id: str,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    resident = _resident_from_actor(session, actor)
    if activity_id not in resident.checked_in_activity_ids:
        raise HTTPException(status_code=403, detail="Circle reveal locked until check-in")
    circle = session.exec(select(Circle).where(Circle.activity_id == activity_id)).first()
    if not circle:
        return ok_response({"activity_id": activity_id, "attendees": []}, request)
    attendee_cards = []
    for resident_id in circle.participant_ids:
        peer = session.get(Resident, resident_id)
        if peer:
            attendee_cards.append(
                {
                    "resident_id": peer.id,
                    "first_name": peer.first_name,
                    "conversation_starter": f"Also likes {', '.join(peer.interests[:2])}" if peer.interests else "",
                }
            )
    return ok_response({"activity_id": activity_id, "attendees": attendee_cards}, request)


@router.post("/activities/{activity_id}/feedback")
def post_feedback(
    activity_id: str,
    payload: FeedbackIn,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    escalation = None
    if payload.safety_report:
        if payload.report_type in {"medical_or_urgent_concern"}:
            escalation = "level_4"
        elif payload.report_type in {"harassment", "felt_unsafe"}:
            escalation = "level_3"
        else:
            escalation = "level_2"
    feedback = Feedback(
        id=deterministic_or_random("feedback"),
        resident_id=actor.actor_id,
        activity_id=activity_id,
        attended=payload.attended,
        felt_after=payload.felt_after,
        activity_fit=payload.activity_fit,
        group_comfort=payload.group_comfort,
        would_repeat=payload.would_repeat,
        safety_report=payload.safety_report,
        report_type=payload.report_type,
        escalation_level=escalation,
        notes=payload.notes,
    )
    session.add(feedback)
    session.commit()
    return ok_response(
        {
            "id": feedback.id,
            "resident_id": feedback.resident_id,
            "activity_id": feedback.activity_id,
            "attended": feedback.attended,
            "felt_after": feedback.felt_after,
            "activity_fit": feedback.activity_fit,
            "group_comfort": feedback.group_comfort,
            "would_repeat": feedback.would_repeat,
            "safety_report": feedback.safety_report,
            "report_type": feedback.report_type,
            "escalation_level": feedback.escalation_level,
            "notes": feedback.notes,
        },
        request,
        status_code=201,
    )


@router.post("/connections/request")
def request_connection(
    payload: ConnectionRequestIn,
    request: Request,
    actor: Actor = Depends(require_role("resident")),
    session: Session = Depends(get_session),
):
    circle = session.exec(select(Circle).where(Circle.activity_id == payload.activity_id)).first()
    if not circle or actor.actor_id not in circle.participant_ids or payload.to_resident_id not in circle.participant_ids:
        raise HTTPException(status_code=403, detail="Connection request allowed only for co-attendees")
    req = ConnectionRequest(
        id=deterministic_or_random("conn"),
        from_resident_id=actor.actor_id,
        to_resident_id=payload.to_resident_id,
        activity_id=payload.activity_id,
    )
    session.add(req)
    session.commit()
    return ok_response(req.model_dump(), request, status_code=201)
