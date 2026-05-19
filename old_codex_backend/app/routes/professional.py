from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import Professional, Resident
from app.routes.common import professional_payload, resident_payload

router = APIRouter(prefix="/api", tags=["professional"])

ALLOWED_PREFERENCE_FIELDS = {
    "preferred_language",
    "location_radius_km",
    "interests",
    "activity_preferences",
    "availability",
    "social_comfort",
    "preferred_group_size",
    "accessibility_needs",
    "cost_sensitivity",
    "avoid",
    "companion_pass_allowed",
    "preference_note",
}

BLOCKED_FIELDS = {
    "diagnosis",
    "diagnoses",
    "therapy_notes",
    "medication_history",
    "clinical_records",
    "medical_notes",
}


class PreferencesPatchIn(BaseModel):
    preferences: dict[str, Any]


@router.get("/professionals/referrals")
def referrals(session: Session = Depends(get_session)) -> list[dict]:
    residents = session.exec(select(Resident)).all()
    payload = []
    for resident in residents:
        if not resident.created_by_professional_id:
            continue
        professional = session.get(Professional, resident.created_by_professional_id)
        payload.append(
            {
                "resident": resident_payload(resident),
                "created_by": professional_payload(professional) if professional else None,
            }
        )
    return payload


@router.patch("/residents/{resident_id}/preferences")
def patch_preferences(resident_id: str, payload: PreferencesPatchIn, session: Session = Depends(get_session)) -> dict:
    resident = session.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    blocked = sorted(set(payload.preferences) & BLOCKED_FIELDS)
    if blocked:
        raise HTTPException(status_code=400, detail=f"Clinical fields are not allowed: {', '.join(blocked)}")

    applied: dict[str, Any] = {}
    for key, value in payload.preferences.items():
        if key not in ALLOWED_PREFERENCE_FIELDS:
            continue
        setattr(resident, key, value)
        applied[key] = value

    session.add(resident)
    session.commit()
    session.refresh(resident)
    return {"resident": resident_payload(resident), "applied": applied}
