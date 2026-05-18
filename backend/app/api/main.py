"""
FastAPI app exposing the GP-onboarding flows.

Endpoints:
- POST /api/professionals/signup    — Track A (verified via stub AGB/BIG/KvK)
- GET  /api/professionals/{id}      — read a single professional
- GET  /api/professionals           — list (optionally filter by status)
- POST /api/referrals               — Track B (consent + resident profile + referral, atomic)
- GET  /api/professionals/{id}/referrals — list referrals submitted by a professional
- GET  /healthz                     — liveness

Connections are per-request via the `get_connection` dependency.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Connection

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status

from app.api.schemas import (
    AvailabilityWindow,
    ConsentResponse,
    ProfessionalResponse,
    ProfessionalSignupRequest,
    ProfessionalSignupResponse,
    ReferralCreateResponse,
    ReferralRequest,
    ReferralResponse,
    ResidentResponse,
    VerificationRecordResponse,
)
from app.db import DEFAULT_DB_PATH, connect, init_db
from app.repositories import (
    ConsentRepository,
    ProfessionalRepository,
    ReferralRepository,
)
from app.services.onboarding_service import (
    OnboardingService,
    ResidentProfileInput,
)

logger = logging.getLogger(__name__)


def get_connection(request: Request) -> Iterator[Connection]:
    db_path: Path = request.app.state.db_path
    conn = connect(db_path=db_path)
    try:
        yield conn
    finally:
        conn.close()


def _professional_to_response(p) -> ProfessionalResponse:
    return ProfessionalResponse(
        id=p.id,
        full_name=p.full_name,
        role=p.role,
        organization=p.organization,
        city=p.city,
        email=p.email,
        verification_status=p.verification_status,
        agb_code=p.agb_code,
        big_number=p.big_number,
        qualification=p.qualification,
        onderneming_agb_code=p.onderneming_agb_code,
        verified_at=p.verified_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def create_app(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    initialize_db: bool = True,
) -> FastAPI:
    app = FastAPI(title="CivicCircles Onboarding API", version="0.1.0")
    app.state.db_path = Path(db_path)
    if initialize_db:
        init_db(db_path=db_path)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/professionals/signup",
        response_model=ProfessionalSignupResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def signup_professional(
        payload: ProfessionalSignupRequest,
        conn: Connection = Depends(get_connection),
    ) -> ProfessionalSignupResponse:
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
            # We persist the rejection but tell the caller it failed.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Professional verification failed",
                    "reason": result.verification.failure_reason,
                    "professional_id": result.professional.id,
                },
            )

        return ProfessionalSignupResponse(
            professional=_professional_to_response(result.professional),
            verification=VerificationRecordResponse(
                id=result.verification.id,
                professional_id=result.verification.professional_id,
                outcome=result.verification.outcome,
                failure_reason=result.verification.failure_reason,
                created_at=result.verification.created_at,
            ),
        )

    @app.get("/api/professionals/{professional_id}", response_model=ProfessionalResponse)
    def get_professional(
        professional_id: str,
        conn: Connection = Depends(get_connection),
    ) -> ProfessionalResponse:
        repo = ProfessionalRepository(conn)
        professional = repo.get_professional(professional_id)
        if professional is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
        return _professional_to_response(professional)

    @app.get("/api/professionals", response_model=list[ProfessionalResponse])
    def list_professionals(
        verification_status: str | None = Query(default=None),
        conn: Connection = Depends(get_connection),
    ) -> list[ProfessionalResponse]:
        repo = ProfessionalRepository(conn)
        if verification_status not in (None, "pending", "approved", "rejected"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid verification_status")
        professionals = repo.list_professionals(verification_status=verification_status)  # type: ignore[arg-type]
        return [_professional_to_response(p) for p in professionals]

    @app.post(
        "/api/referrals",
        response_model=ReferralCreateResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_referral(
        payload: ReferralRequest,
        conn: Connection = Depends(get_connection),
    ) -> ReferralCreateResponse:
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
                    availability=tuple(_avail_to_tuple(a) for a in profile.availability),
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

        consent_repo = ConsentRepository(conn)
        scopes = [s.scope for s in consent_repo.list_scopes(result.consent.id)]
        return ReferralCreateResponse(
            resident=ResidentResponse(
                id=result.resident.id,
                first_name=result.resident.first_name,
                email=result.resident.email,
                preferred_language=result.resident.preferred_language,
                city=result.resident.city,
                neighborhood=result.resident.neighborhood,
                location_radius_km=result.resident.location_radius_km,
                social_comfort=result.resident.social_comfort,
                preferred_group_size_min=result.resident.preferred_group_size_min,
                preferred_group_size_max=result.resident.preferred_group_size_max,
                cost_sensitivity=result.resident.cost_sensitivity,
                status=result.resident.status,
                created_at=result.resident.created_at,
                updated_at=result.resident.updated_at,
            ),
            consent=ConsentResponse(
                id=result.consent.id,
                resident_id=result.consent.resident_id,
                professional_id=result.consent.professional_id,
                status=result.consent.status,
                granted_at=result.consent.granted_at,
                consent_text_version=result.consent.consent_text_version,
                consent_locale=result.consent.consent_locale,
                capture_method=result.consent.capture_method,
                scopes=scopes,  # type: ignore[arg-type]
            ),
            referral=ReferralResponse(
                id=result.referral.id,
                resident_id=result.referral.resident_id,
                professional_id=result.referral.professional_id,
                referral_reason=result.referral.referral_reason,
                status=result.referral.status,
                created_at=result.referral.created_at,
            ),
        )

    @app.get(
        "/api/professionals/{professional_id}/referrals",
        response_model=list[ReferralResponse],
    )
    def list_referrals(
        professional_id: str,
        conn: Connection = Depends(get_connection),
    ) -> list[ReferralResponse]:
        prof_repo = ProfessionalRepository(conn)
        if prof_repo.get_professional(professional_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Professional not found")
        repo = ReferralRepository(conn)
        referrals = repo.list_for_professional(professional_id)
        return [
            ReferralResponse(
                id=r.id,
                resident_id=r.resident_id,
                professional_id=r.professional_id,
                referral_reason=r.referral_reason,
                status=r.status,
                created_at=r.created_at,
            )
            for r in referrals
        ]

    return app


def _avail_to_tuple(a: AvailabilityWindow) -> tuple[str, str, str]:
    return (a.weekday, a.start_time_local, a.end_time_local)
