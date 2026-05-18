from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Activity, Circle, CircleMember, Feedback, Invitation, Professional, Proposal, Resident

DEMO_RESIDENT_ID = "resident_sofia"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_demo_resident(session: Session) -> Resident:
    resident = session.get(Resident, DEMO_RESIDENT_ID)
    if not resident:
        raise HTTPException(status_code=404, detail="Demo resident not found")
    return resident


def get_activity(session: Session, activity_id: str) -> Activity:
    activity = session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


def activity_payload(activity: Activity) -> dict:
    return {
        "id": activity.id,
        "title": activity.title,
        "activity_type": activity.activity_type,
        "date_time_label": activity.date_time_label,
        "availability_label": activity.availability_label,
        "location": {
            "name": activity.location_name,
            "address": activity.address,
            "lat": activity.lat,
            "lng": activity.lng,
        },
        "group_size": activity.group_size,
        "pace": activity.pace,
        "intensity": activity.intensity,
        "host": activity.host,
        "cost": activity.cost_label,
        "cost_amount": activity.cost_amount,
        "accessibility": activity.accessibility,
        "alcohol_free": activity.alcohol_free,
        "tags": activity.tags,
        "status": activity.status,
        "why_fit": activity.why_fit,
    }


def resident_payload(resident: Resident) -> dict:
    return {
        "id": resident.id,
        "first_name": resident.first_name,
        "email": resident.email,
        "preferred_language": resident.preferred_language,
        "approx_location": resident.approx_location,
        "location_radius_km": resident.location_radius_km,
        "interests": resident.interests,
        "activity_preferences": resident.activity_preferences,
        "availability": resident.availability,
        "social_comfort": resident.social_comfort,
        "preferred_group_size": resident.preferred_group_size,
        "accessibility_needs": resident.accessibility_needs,
        "cost_sensitivity": resident.cost_sensitivity,
        "avoid": resident.avoid,
        "companion_pass_allowed": resident.companion_pass_allowed,
        "status": resident.status,
        "consent_scopes": resident.consent_scopes,
        "created_by_professional_id": resident.created_by_professional_id,
        "preference_note": resident.preference_note,
    }


def professional_payload(professional: Professional) -> dict:
    return {
        "id": professional.id,
        "name": professional.name,
        "role": professional.role,
        "organization": professional.organization,
        "city": professional.city,
        "verification_status": professional.verification_status,
        "email": professional.email,
    }


def invitation_payload(session: Session, invitation: Invitation) -> dict:
    activity = get_activity(session, invitation.activity_id)
    return {
        "id": invitation.id,
        "resident_id": invitation.resident_id,
        "activity_id": invitation.activity_id,
        "status": invitation.status,
        "companion_pass_available": invitation.companion_pass_available,
        "accepted_at": invitation.accepted_at,
        "declined_at": invitation.declined_at,
        "activity": activity_payload(activity),
    }


def proposal_payload(session: Session, proposal: Proposal) -> dict:
    activity = get_activity(session, proposal.activity_id)
    return {
        "id": proposal.id,
        "activity_id": proposal.activity_id,
        "title": proposal.title,
        "status": proposal.status,
        "generated_summary": proposal.generated_summary,
        "human_approval_status": proposal.human_approval_status,
        "ranking_score": proposal.ranking_score,
        "alternative_notes": proposal.alternative_notes,
        "activity": activity_payload(activity),
    }


def activity_circle(session: Session, activity_id: str) -> Circle:
    circle = session.exec(select(Circle).where(Circle.activity_id == activity_id)).first()
    if not circle:
        raise HTTPException(status_code=404, detail="Circle not found")
    return circle


def feedback_for_residents(session: Session, residents: list[Resident]) -> list[Feedback]:
    ids = [resident.id for resident in residents]
    if not ids:
        return []
    return session.exec(select(Feedback).where(Feedback.resident_id.in_(ids))).all()


def circle_members(session: Session, circle_id: str) -> list[CircleMember]:
    return session.exec(select(CircleMember).where(CircleMember.circle_id == circle_id)).all()
