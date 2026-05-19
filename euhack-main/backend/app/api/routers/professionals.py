from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import schemas
from app.api.converters import (
    professional_to_response,
    referral_to_response,
    verification_to_response,
)
from app.api.deps import get_connection
from app.repositories import ProfessionalRepository, ReferralRepository
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/api/professionals", tags=["professionals"])


@router.post(
    "/signup",
    response_model=schemas.ProfessionalSignupResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup_professional(
    payload: schemas.ProfessionalSignupRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ProfessionalSignupResponse:
    service = OnboardingService(conn)
    try:
        result = service.signup_professional(
            full_name=payload.full_name,
            role=payload.role,
            email=payload.email,
            agb_code=payload.agb_code,
            big_number=payload.big_number,
            kvk_number=payload.kvk_number,
            organization=payload.organization,
            city=payload.city,
            qualification_hint=payload.qualification_hint,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if result.verification.outcome == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Professional verification failed",
                "reason": result.verification.failure_reason,
                "professional_id": result.professional.id,
            },
        )

    return schemas.ProfessionalSignupResponse(
        professional=professional_to_response(result.professional),
        verification=verification_to_response(result.verification),
    )


@router.get("", response_model=list[schemas.ProfessionalResponse])
def list_professionals(
    verification_status: str | None = Query(default=None),
    conn: Connection = Depends(get_connection),
) -> list[schemas.ProfessionalResponse]:
    repo = ProfessionalRepository(conn)
    if verification_status not in (None, "pending", "approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid verification_status",
        )
    return [
        professional_to_response(p)
        for p in repo.list_professionals(verification_status=verification_status)  # type: ignore[arg-type]
    ]


@router.get("/{professional_id}", response_model=schemas.ProfessionalResponse)
def get_professional(
    professional_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ProfessionalResponse:
    repo = ProfessionalRepository(conn)
    professional = repo.get_professional(professional_id)
    if professional is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
    return professional_to_response(professional)


@router.get(
    "/{professional_id}/referrals",
    response_model=list[schemas.ReferralResponse],
)
def list_referrals_for_professional(
    professional_id: str,
    conn: Connection = Depends(get_connection),
) -> list[schemas.ReferralResponse]:
    prof_repo = ProfessionalRepository(conn)
    if prof_repo.get_professional(professional_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
    referrals = ReferralRepository(conn).list_for_professional(professional_id)
    return [referral_to_response(r) for r in referrals]
