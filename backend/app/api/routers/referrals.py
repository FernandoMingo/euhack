from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import schemas
from app.api.converters import (
    consent_to_response,
    referral_to_response,
    resident_to_response,
)
from app.api.deps import get_connection
from app.repositories import ConsentRepository, ReferralRepository
from app.services.onboarding_service import OnboardingService, ResidentProfileInput

router = APIRouter(prefix="/api/referrals", tags=["referrals"])


def _avail_tuple(window: schemas.AvailabilityWindow) -> tuple[str, str, str]:
    return (window.weekday, window.start_time_local, window.end_time_local)


@router.post(
    "",
    response_model=schemas.ReferralCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_referral(
    payload: schemas.ReferralRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ReferralCreateResponse:
    service = OnboardingService(conn)
    profile = payload.profile
    try:
        result = service.create_referral(
            professional_id=payload.professional_id,
            profile=ResidentProfileInput(
                first_name=profile.first_name,
                email=profile.email,
                preferred_language=profile.preferred_language,
                city=profile.city,
                social_comfort=profile.social_comfort,
                preferred_group_size_min=profile.preferred_group_size_min,
                preferred_group_size_max=profile.preferred_group_size_max,
                cost_sensitivity=profile.cost_sensitivity,
                neighborhood=profile.neighborhood,
                location_radius_km=profile.location_radius_km,
                interests=tuple(profile.interests),
                activities=tuple(profile.activities),
                accessibility_needs=tuple(profile.accessibility_needs),
                availability=tuple(_avail_tuple(a) for a in profile.availability),
                avoidances=tuple(profile.avoidances),
            ),
            consent_scopes=payload.consent_scopes,
            referral_reason=payload.referral_reason,
            consent_text_version=payload.consent_text_version,
            consent_locale=payload.consent_locale,
            capture_method=payload.capture_method,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    scopes = ConsentRepository(conn).list_scopes(result.consent.id)
    return schemas.ReferralCreateResponse(
        resident=resident_to_response(result.resident),
        consent=consent_to_response(result.consent, scopes),
        referral=referral_to_response(result.referral),
    )


@router.get("/{referral_id}", response_model=schemas.ReferralResponse)
def get_referral(
    referral_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ReferralResponse:
    referral = ReferralRepository(conn).get_referral(referral_id)
    if referral is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    return referral_to_response(referral)


@router.patch("/{referral_id}/status", response_model=schemas.ReferralResponse)
def update_referral_status(
    referral_id: str,
    payload: schemas.ReferralStatusUpdateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ReferralResponse:
    repo = ReferralRepository(conn)
    if repo.get_referral(referral_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    repo.update_status(referral_id=referral_id, status=payload.status)
    conn.commit()
    updated = repo.get_referral(referral_id)
    assert updated is not None
    return referral_to_response(updated)
