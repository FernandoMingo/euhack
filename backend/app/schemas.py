from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProfessionalSignupIn(BaseModel):
    id: str
    name: str
    role: str
    organization: str
    city: str
    email: str


class ResidentReferralIn(BaseModel):
    resident_id: str
    first_name: str
    email: str
    preferred_language: str = "English"
    consent_scope: list[str] = Field(default_factory=list)
    consent_given: bool = True


class ResidentProfileIn(BaseModel):
    approx_location: dict[str, Any]
    location_radius_km: int
    interests: list[str]
    activity_preferences: list[str]
    availability: list[str]
    social_comfort: str
    preferred_group_size: dict[str, int]
    accessibility_needs: list[str] = Field(default_factory=list)
    cost_sensitivity: str = "free_or_low_cost"
    avoid: list[str] = Field(default_factory=list)
    profile_visibility: dict[str, Any] = Field(default_factory=dict)


class ResidentPreferencePatchIn(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class CompanionPassIn(BaseModel):
    guest_name: str


class FeedbackIn(BaseModel):
    attended: bool
    felt_after: str
    activity_fit: str
    group_comfort: str
    would_repeat: bool
    safety_report: bool = False
    report_type: str | None = None
    notes: str | None = None


class ConnectionRequestIn(BaseModel):
    to_resident_id: str
    activity_id: str


class ProposalPatchIn(BaseModel):
    start_time: str | None = None
    capacity: int | None = None
    location_name: str | None = None
    reason_code: str = "OPERATOR_EDIT"


class ProposalDecisionIn(BaseModel):
    reason_code: str = "OPERATOR_DECISION"


class GenerateCirclesIn(BaseModel):
    resident_ids: list[str] | None = None


class RankActivitiesIn(BaseModel):
    resident_ids: list[str]
    activity_ids: list[str] | None = None


class ExplainMatchIn(BaseModel):
    resident_ids: list[str]
    activity_id: str


class UpdatePreferencesFromFeedbackIn(BaseModel):
    resident_id: str
