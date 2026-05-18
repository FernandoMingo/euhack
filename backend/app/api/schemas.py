"""
Pydantic request/response models for the onboarding API.

These intentionally mirror the dataclasses in app.dataclasses one-for-one
rather than reusing them directly — the dataclasses model the database
row, the pydantic models model the wire format, and the two should be
free to diverge.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

CaptureMethodLiteral = Literal["in_consult", "self_completion"]
VerificationStatusLiteral = Literal["pending", "approved", "rejected"]
VerificationOutcomeLiteral = Literal["passed", "failed"]

ConsentScopeLiteral = Literal[
    "create_social_profile",
    "use_profile_for_activity_matching",
    "send_activity_invitations",
    "share_limited_status_with_professional",
    "internal_peer_ratings",
]


# ---------- Professional signup ----------


class ProfessionalSignupRequest(BaseModel):
    full_name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    email: EmailStr
    agb_code: str = Field(min_length=8, max_length=8)
    big_number: str | None = None
    kvk_number: str | None = None
    organization: str | None = None
    city: str | None = None
    qualification_hint: str | None = None


class ProfessionalResponse(BaseModel):
    id: str
    full_name: str
    role: str
    organization: str | None
    city: str | None
    email: str
    verification_status: VerificationStatusLiteral
    agb_code: str | None
    big_number: str | None
    qualification: str | None
    onderneming_agb_code: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VerificationRecordResponse(BaseModel):
    id: str
    professional_id: str
    outcome: VerificationOutcomeLiteral
    failure_reason: str | None
    created_at: datetime


class ProfessionalSignupResponse(BaseModel):
    professional: ProfessionalResponse
    verification: VerificationRecordResponse


# ---------- Resident referral ----------


class AvailabilityWindow(BaseModel):
    weekday: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    start_time_local: str
    end_time_local: str


class ResidentProfilePayload(BaseModel):
    first_name: str = Field(min_length=1)
    email: EmailStr
    preferred_language: str = Field(min_length=1)
    city: str = Field(min_length=1)
    social_comfort: str = Field(min_length=1)
    preferred_group_size_min: int = Field(ge=1)
    preferred_group_size_max: int = Field(ge=1)
    cost_sensitivity: str = Field(min_length=1)
    neighborhood: str | None = None
    location_radius_km: int = Field(default=3, ge=0)
    interests: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)
    availability: list[AvailabilityWindow] = Field(default_factory=list)
    avoidances: list[str] = Field(default_factory=list)


class ReferralRequest(BaseModel):
    professional_id: str = Field(min_length=1)
    profile: ResidentProfilePayload
    consent_scopes: list[ConsentScopeLiteral] = Field(
        default_factory=lambda: [
            "create_social_profile",
            "use_profile_for_activity_matching",
            "send_activity_invitations",
            "share_limited_status_with_professional",
        ]
    )
    consent_text_version: str = "v1.0-nl-2026-05"
    consent_locale: str = "nl"
    capture_method: CaptureMethodLiteral = "in_consult"
    referral_reason: str | None = None


class ResidentResponse(BaseModel):
    id: str
    first_name: str
    email: str
    preferred_language: str
    city: str
    neighborhood: str | None
    location_radius_km: int
    social_comfort: str
    preferred_group_size_min: int
    preferred_group_size_max: int
    cost_sensitivity: str
    status: Literal["active", "paused", "withdrawn"]
    created_at: datetime
    updated_at: datetime


class ConsentResponse(BaseModel):
    id: str
    resident_id: str
    professional_id: str
    status: Literal["active", "revoked"]
    granted_at: datetime
    consent_text_version: str
    consent_locale: str
    capture_method: CaptureMethodLiteral
    scopes: list[ConsentScopeLiteral]


class ReferralResponse(BaseModel):
    id: str
    resident_id: str
    professional_id: str
    referral_reason: str | None
    status: Literal["submitted", "accepted", "closed"]
    created_at: datetime


class ReferralCreateResponse(BaseModel):
    resident: ResidentResponse
    consent: ConsentResponse
    referral: ReferralResponse
