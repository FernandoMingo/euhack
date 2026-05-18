from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import CircleMember, Feedback, Invitation, Resident
from app.routes.common import (
    DEMO_RESIDENT_ID,
    activity_circle,
    circle_members,
    get_demo_resident,
    invitation_payload,
    now_utc,
    resident_payload,
)

router = APIRouter(prefix="/api", tags=["resident"])


class FeedbackIn(BaseModel):
    felt_after: str
    would_do_similar_again: str
    preference_adjustment: str | None = None


@router.get("/resident/me")
def resident_me(session: Session = Depends(get_session)) -> dict:
    return resident_payload(get_demo_resident(session))


@router.get("/resident/invitations")
def resident_invitations(session: Session = Depends(get_session)) -> list[dict]:
    invitations = session.exec(select(Invitation).where(Invitation.resident_id == DEMO_RESIDENT_ID)).all()
    return [invitation_payload(session, invitation) for invitation in invitations]


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: str, session: Session = Depends(get_session)) -> dict:
    invitation = session.get(Invitation, invitation_id)
    if not invitation or invitation.resident_id != DEMO_RESIDENT_ID:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "accepted"
    invitation.accepted_at = now_utc()
    invitation.declined_at = None
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return invitation_payload(session, invitation)


@router.post("/invitations/{invitation_id}/decline")
def decline_invitation(invitation_id: str, session: Session = Depends(get_session)) -> dict:
    invitation = session.get(Invitation, invitation_id)
    if not invitation or invitation.resident_id != DEMO_RESIDENT_ID:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "declined"
    invitation.declined_at = now_utc()
    invitation.accepted_at = None
    session.add(invitation)
    session.commit()
    session.refresh(invitation)
    return invitation_payload(session, invitation)


@router.post("/activities/{activity_id}/check-in")
def check_in(activity_id: str, session: Session = Depends(get_session)) -> dict:
    resident = get_demo_resident(session)
    circle = activity_circle(session, activity_id)
    member = session.exec(
        select(CircleMember).where(
            CircleMember.circle_id == circle.id,
            CircleMember.resident_id == resident.id,
        )
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Resident is not in this circle")
    member.checked_in = True
    checked = set(resident.checked_in_activity_ids)
    checked.add(activity_id)
    resident.checked_in_activity_ids = sorted(checked)
    resident.updated_at = now_utc()
    session.add(member)
    session.add(resident)
    session.commit()
    return {"activity_id": activity_id, "checked_in": True, "circle_reveal_unlocked": True}


@router.get("/activities/{activity_id}/circle-reveal")
def circle_reveal(activity_id: str, session: Session = Depends(get_session)) -> dict:
    resident = get_demo_resident(session)
    circle = activity_circle(session, activity_id)
    checked_in = activity_id in resident.checked_in_activity_ids
    if not checked_in:
        return {"activity_id": activity_id, "locked": True, "attendees": []}

    attendees = []
    for member in circle_members(session, circle.id):
        if member.resident_id == DEMO_RESIDENT_ID or not member.consent_reveal:
            continue
        attendees.append(
            {
                "first_name": member.reveal_first_name,
                "short_bio": member.short_bio,
                "conversation_starter": member.conversation_starter,
            }
        )
    return {"activity_id": activity_id, "locked": False, "attendees": attendees}


@router.post("/activities/{activity_id}/feedback")
def submit_feedback(activity_id: str, payload: FeedbackIn, session: Session = Depends(get_session)) -> dict:
    resident = session.get(Resident, DEMO_RESIDENT_ID)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    count = len(session.exec(select(Feedback).where(Feedback.resident_id == DEMO_RESIDENT_ID)).all()) + 1
    feedback = Feedback(
        id=f"feedback_sofia_{count}",
        resident_id=DEMO_RESIDENT_ID,
        activity_id=activity_id,
        felt_after=payload.felt_after,
        would_do_similar_again=payload.would_do_similar_again,
        preference_adjustment=payload.preference_adjustment,
    )
    if payload.preference_adjustment:
        resident.preference_note = payload.preference_adjustment
        resident.updated_at = now_utc()
        session.add(resident)
    session.add(feedback)
    session.commit()
    return {
        "id": feedback.id,
        "activity_id": feedback.activity_id,
        "felt_after": feedback.felt_after,
        "would_do_similar_again": feedback.would_do_similar_again,
        "preference_adjustment": feedback.preference_adjustment,
    }
