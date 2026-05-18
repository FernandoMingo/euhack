"""
Onboarding service. Composes repository operations into the two flows
described in the GP-onboarding briefing:

Track A — Professional onboarding
  signup_professional() runs Vektis AGB / CIBG BIG / KvK verification through
  the injected verifier, records the verification attempt, and (on success)
  flips the professional to 'approved'. On failure the professional row is
  still created with status 'rejected' so audit history is preserved.

Track B — Resident referral
  create_referral() is the 90-second moment from the briefing §3.2:
    1) explicit consent recorded against the consent_text version shown,
    2) lightweight resident profile created (no clinical data),
    3) referral submitted to the welzijnscoach chain.
  The three writes happen in one transaction so a failure mid-way leaves
  no orphan rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from sqlite3 import Connection

from app.dataclasses import (
    CaptureMethod,
    ConsentRecord,
    ProfessionalVerification,
    Referral,
    Resident,
    TrustedProfessional,
)
from app.repositories import (
    ConsentRepository,
    ProfessionalRepository,
    ReferralRepository,
    ResidentRepository,
)
from app.services.verification_service import (
    StubVerificationService,
    VerificationFailure,
)

DEFAULT_REFERRAL_SCOPES: tuple[str, ...] = (
    "create_social_profile",
    "use_profile_for_activity_matching",
    "send_activity_invitations",
    "share_limited_status_with_professional",
)


@dataclass(slots=True)
class ProfessionalSignupResult:
    professional: TrustedProfessional
    verification: ProfessionalVerification


@dataclass(slots=True)
class ResidentProfileInput:
    first_name: str
    email: str
    preferred_language: str
    city: str
    social_comfort: str
    preferred_group_size_min: int
    preferred_group_size_max: int
    cost_sensitivity: str
    neighborhood: str | None = None
    location_radius_km: int = 3
    interests: tuple[str, ...] = ()
    activities: tuple[str, ...] = ()
    accessibility_needs: tuple[str, ...] = ()
    availability: tuple[tuple[str, str, str], ...] = ()  # (weekday, start, end)
    avoidances: tuple[str, ...] = ()


@dataclass(slots=True)
class ReferralResult:
    resident: Resident
    consent: ConsentRecord
    referral: Referral


class OnboardingService:
    """
    Stateless service. Holds a sqlite3.Connection so all writes within
    a single call share one transaction.
    """

    def __init__(
        self,
        conn: Connection,
        *,
        verifier: StubVerificationService | None = None,
    ) -> None:
        self.conn = conn
        self.verifier = verifier or StubVerificationService()
        self.professionals = ProfessionalRepository(conn)
        self.residents = ResidentRepository(conn)
        self.consents = ConsentRepository(conn)
        self.referrals = ReferralRepository(conn)

    # ---------- Track A: professional onboarding ----------

    def signup_professional(
        self,
        *,
        full_name: str,
        role: str,
        email: str,
        agb_code: str,
        big_number: str | None = None,
        kvk_number: str | None = None,
        organization: str | None = None,
        city: str | None = None,
        qualification_hint: str | None = None,
    ) -> ProfessionalSignupResult:
        existing = self.professionals.get_professional_by_email(email)
        if existing is not None:
            raise ValueError(f"Professional with email {email!r} already exists")
        if self.professionals.get_professional_by_agb(agb_code) is not None:
            raise ValueError(f"Professional with AGB code {agb_code!r} already exists")

        professional = self.professionals.create_professional(
            full_name=full_name,
            role=role,
            email=email,
            organization=organization,
            city=city,
            agb_code=agb_code,
            big_number=big_number,
            qualification=qualification_hint,
        )

        try:
            result = self.verifier.verify(
                agb_code=agb_code,
                big_number=big_number,
                kvk_number=kvk_number,
                qualification_hint=qualification_hint,
            )
        except VerificationFailure as failure:
            verification = self.professionals.record_verification(
                professional_id=professional.id,
                outcome="failed",
                failure_reason=str(failure),
            )
            self.professionals.mark_rejected(professional_id=professional.id)
            self.conn.commit()
            rejected = self.professionals.get_professional(professional.id)
            assert rejected is not None
            return ProfessionalSignupResult(professional=rejected, verification=verification)

        verification = self.professionals.record_verification(
            professional_id=professional.id,
            outcome="passed",
            agb_response_json=result.agb_response_json,
            big_response_json=result.big_response_json,
            kvk_response_json=result.kvk_response_json,
        )
        self.professionals.mark_verified(
            professional_id=professional.id,
            qualification=result.qualification,
            onderneming_agb_code=result.onderneming_agb_code,
        )
        self.conn.commit()
        approved = self.professionals.get_professional(professional.id)
        assert approved is not None
        return ProfessionalSignupResult(professional=approved, verification=verification)

    # ---------- Track B: resident referral ----------

    def create_referral(
        self,
        *,
        professional_id: str,
        profile: ResidentProfileInput,
        consent_scopes: Iterable[str] = DEFAULT_REFERRAL_SCOPES,
        referral_reason: str | None = None,
        consent_text_version: str = "v1.0-nl-2026-05",
        consent_locale: str = "nl",
        capture_method: CaptureMethod = "in_consult",
    ) -> ReferralResult:
        professional = self.professionals.get_professional(professional_id)
        if professional is None:
            raise ValueError(f"Unknown professional {professional_id!r}")
        if professional.verification_status != "approved":
            raise ValueError(
                f"Professional {professional_id!r} is not approved "
                f"(status={professional.verification_status!r})"
            )

        scope_list = list(dict.fromkeys(consent_scopes))
        if not scope_list:
            raise ValueError("Referral requires at least one consent scope")

        try:
            resident = self.residents.create_resident(
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
            )
            for interest in profile.interests:
                self.residents.add_preference(
                    resident_id=resident.id,
                    preference_type="interest",
                    value=interest,
                )
            for activity in profile.activities:
                self.residents.add_preference(
                    resident_id=resident.id,
                    preference_type="activity",
                    value=activity,
                )
            for need in profile.accessibility_needs:
                self.residents.add_preference(
                    resident_id=resident.id,
                    preference_type="accessibility_need",
                    value=need,
                )
            for weekday, start, end in profile.availability:
                self.residents.add_availability(
                    resident_id=resident.id,
                    weekday=weekday,
                    start_time_local=start,
                    end_time_local=end,
                )
            for avoid in profile.avoidances:
                self.residents.add_avoidance(resident_id=resident.id, value=avoid)

            consent = self.consents.create_consent(
                resident_id=resident.id,
                professional_id=professional_id,
                scopes=scope_list,
                consent_text_version=consent_text_version,
                consent_locale=consent_locale,
                capture_method=capture_method,
            )
            referral = self.referrals.create_referral(
                resident_id=resident.id,
                professional_id=professional_id,
                referral_reason=referral_reason,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return ReferralResult(resident=resident, consent=consent, referral=referral)
