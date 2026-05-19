from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr

from app.api import schemas
from app.api.converters import (
    availability_to_response,
    avoidance_to_response,
    consent_to_response,
    preference_to_response,
    resident_to_response,
)
from app.api.deps import get_connection
from app.repositories import ConsentRepository, ResidentRepository

router = APIRouter(prefix="/api/residents", tags=["residents"])


class ResidentLoginRequest(BaseModel):
    email: EmailStr


@router.post(
    "/login",
    response_model=schemas.ResidentResponse,
    summary="Look up a resident by their registered email (demo login)",
)
def login_resident(
    payload: ResidentLoginRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentResponse:
    """Demo-only email-based login.

    The resident is created during the GP referral flow with the email the
    huisarts entered. We look them up by that email and return their public
    profile. The frontend stores the returned ``id`` in localStorage and uses
    it to scope every subsequent ``/api/.../{resident_id}/...`` call.

    There is no password in the prototype. Real deployments would gate this
    with a magic-link or DigiD step.
    """
    resident = ResidentRepository(conn).get_resident_by_email(payload.email)
    if resident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CivicCircles account is linked to this email yet.",
        )
    if resident.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not active.",
        )
    return resident_to_response(resident)


@router.get("", response_model=list[schemas.ResidentResponse])
def list_residents(
    status_filter: schemas.ResidentStatusLiteral | None = Query(default=None, alias="status"),
    conn: Connection = Depends(get_connection),
) -> list[schemas.ResidentResponse]:
    repo = ResidentRepository(conn)
    residents = repo.list_residents(status=status_filter)
    return [resident_to_response(r) for r in residents]


@router.get("/{resident_id}", response_model=schemas.ResidentResponse)
def get_resident(
    resident_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentResponse:
    resident = ResidentRepository(conn).get_resident(resident_id)
    if resident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    return resident_to_response(resident)


@router.patch("/{resident_id}/status", response_model=schemas.ResidentResponse)
def update_resident_status(
    resident_id: str,
    payload: schemas.ResidentStatusUpdateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentResponse:
    repo = ResidentRepository(conn)
    if repo.get_resident(resident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    repo.update_resident_status(resident_id=resident_id, status=payload.status)
    conn.commit()
    updated = repo.get_resident(resident_id)
    assert updated is not None
    return resident_to_response(updated)


@router.post(
    "/{resident_id}/preferences",
    response_model=schemas.ResidentPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_preference(
    resident_id: str,
    payload: schemas.ResidentPreferenceRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentPreferenceResponse:
    repo = ResidentRepository(conn)
    if repo.get_resident(resident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    preference = repo.add_preference(
        resident_id=resident_id,
        preference_type=payload.preference_type,
        value=payload.value,
    )
    conn.commit()
    return preference_to_response(preference)


@router.post(
    "/{resident_id}/availability",
    response_model=schemas.ResidentAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_availability(
    resident_id: str,
    payload: schemas.ResidentAvailabilityRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentAvailabilityResponse:
    repo = ResidentRepository(conn)
    if repo.get_resident(resident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    availability = repo.add_availability(
        resident_id=resident_id,
        weekday=payload.weekday,
        start_time_local=payload.start_time_local,
        end_time_local=payload.end_time_local,
    )
    conn.commit()
    return availability_to_response(availability)


@router.post(
    "/{resident_id}/avoidances",
    response_model=schemas.ResidentAvoidanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_avoidance(
    resident_id: str,
    payload: schemas.ResidentAvoidanceRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentAvoidanceResponse:
    repo = ResidentRepository(conn)
    if repo.get_resident(resident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    avoidance = repo.add_avoidance(resident_id=resident_id, value=payload.value)
    conn.commit()
    return avoidance_to_response(avoidance)


@router.get(
    "/{resident_id}/consents",
    response_model=list[schemas.ConsentResponse],
)
def list_resident_consents(
    resident_id: str,
    conn: Connection = Depends(get_connection),
) -> list[schemas.ConsentResponse]:
    if ResidentRepository(conn).get_resident(resident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    consents_repo = ConsentRepository(conn)
    consents = consents_repo.list_active_for_resident(resident_id)
    return [consent_to_response(c, consents_repo.list_scopes(c.id)) for c in consents]
