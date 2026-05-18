from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.api.common import deterministic_or_random, now_utc
from app.core.auth import Actor, require_role
from app.core.response import ok_response
from app.db import get_session
from app.models import ConsentRecord, Professional, Resident
from app.schemas import ProfessionalSignupIn, ResidentPreferencePatchIn, ResidentProfileIn, ResidentReferralIn
from app.services.policy import sanitize_preferences_update

router = APIRouter(prefix="/api", tags=["professional"])


@router.post("/professionals/signup")
def signup_professional(payload: ProfessionalSignupIn, request: Request, session: Session = Depends(get_session)):
    prof = Professional(
        id=payload.id,
        name=payload.name,
        role=payload.role,
        organization=payload.organization,
        city=payload.city,
        email=payload.email,
    )
    session.merge(prof)
    session.commit()
    session.refresh(prof)
    return ok_response(prof.model_dump(), request, status_code=201)


@router.get("/professionals/me")
def professional_me(
    request: Request,
    actor: Actor = Depends(require_role("professional")),
    session: Session = Depends(get_session),
):
    prof = session.get(Professional, actor.actor_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Professional not found")
    return ok_response(prof.model_dump(), request)


@router.post("/residents/referral")
def create_referral(
    payload: ResidentReferralIn,
    request: Request,
    actor: Actor = Depends(require_role("professional")),
    session: Session = Depends(get_session),
):
    if not payload.consent_given:
        raise HTTPException(status_code=400, detail="Consent is required to create referral")
    resident = Resident(
        id=payload.resident_id,
        first_name=payload.first_name,
        email=payload.email,
        preferred_language=payload.preferred_language,
        profile_visibility={
            "photo": True,
            "first_name": True,
            "short_bio": True,
            "conversation_starter": True,
        },
    )
    session.merge(resident)
    consent = ConsentRecord(
        id=deterministic_or_random("consent"),
        resident_id=payload.resident_id,
        professional_id=actor.actor_id,
        consent_scope=payload.consent_scope or [
            "create_social_profile",
            "use_profile_for_activity_matching",
            "send_activity_invitations",
            "share_limited_status_with_professional",
        ],
    )
    session.add(consent)
    session.commit()
    return ok_response({"resident_id": resident.id, "consent_id": consent.id}, request, status_code=201)


def _require_active_consent(session: Session, resident_id: str) -> None:
    consent = session.exec(
        select(ConsentRecord).where(ConsentRecord.resident_id == resident_id, ConsentRecord.revoked_at.is_(None))
    ).first()
    if not consent:
        raise HTTPException(status_code=403, detail="No active consent for resident")


@router.post("/residents/{resident_id}/profile")
def create_or_update_profile(
    resident_id: str,
    payload: ResidentProfileIn,
    request: Request,
    actor: Actor = Depends(require_role("professional")),
    session: Session = Depends(get_session),
):
    _require_active_consent(session, resident_id)
    resident = session.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    resident.approx_location = payload.approx_location
    resident.location_radius_km = payload.location_radius_km
    resident.interests = payload.interests
    resident.activity_preferences = payload.activity_preferences
    resident.availability = payload.availability
    resident.social_comfort = payload.social_comfort
    resident.preferred_group_size = payload.preferred_group_size
    resident.accessibility_needs = payload.accessibility_needs
    resident.cost_sensitivity = payload.cost_sensitivity
    resident.avoid = payload.avoid
    resident.profile_visibility = payload.profile_visibility
    resident.updated_at = now_utc()
    session.add(resident)
    session.commit()
    session.refresh(resident)
    return ok_response(resident.model_dump(), request)


@router.get("/professionals/referrals")
def list_referrals(
    request: Request,
    actor: Actor = Depends(require_role("professional")),
    session: Session = Depends(get_session),
):
    consents = session.exec(select(ConsentRecord).where(ConsentRecord.professional_id == actor.actor_id)).all()
    resident_ids = [c.resident_id for c in consents]
    residents = [session.get(Resident, rid) for rid in resident_ids]
    payload = [r.model_dump() for r in residents if r]
    return ok_response(payload, request)


@router.patch("/residents/{resident_id}/preferences")
def patch_preferences(
    resident_id: str,
    payload: ResidentPreferencePatchIn,
    request: Request,
    actor: Actor = Depends(require_role("professional")),
    session: Session = Depends(get_session),
):
    _require_active_consent(session, resident_id)
    resident = session.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    safe_prefs = sanitize_preferences_update(payload.preferences)
    resident.preferences_extra = {**resident.preferences_extra, **safe_prefs}
    resident.updated_at = now_utc()
    session.add(resident)
    session.commit()
    return ok_response(
        {"resident_id": resident_id, "preferences": resident.preferences_extra, "updated_by": actor.actor_id},
        request,
    )
