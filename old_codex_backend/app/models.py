from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Resident(SQLModel, table=True):
    id: str = Field(primary_key=True)
    first_name: str
    email: str = Field(index=True)
    preferred_language: str
    approx_location: str
    location_radius_km: int
    location_lat: float
    location_lng: float
    interests: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    activity_preferences: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    availability: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    social_comfort: str
    preferred_group_size: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON))
    accessibility_needs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cost_sensitivity: str
    avoid: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    companion_pass_allowed: bool = True
    status: str = "active"
    consent_scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_by_professional_id: str | None = Field(default=None, index=True)
    short_bio: str = ""
    conversation_starter: str = ""
    preference_note: str = ""
    checked_in_activity_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Professional(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    role: str
    organization: str
    city: str
    verification_status: str
    email: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class Activity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    activity_type: str
    date_time_label: str
    availability_label: str
    location_name: str
    address: str
    lat: float
    lng: float
    group_size: int
    pace: str
    intensity: str
    host: str
    cost_label: str
    cost_amount: float
    accessibility: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    alcohol_free: bool = True
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "proposed"
    why_fit: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Invitation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resident_id: str = Field(index=True)
    activity_id: str = Field(index=True)
    status: str = "sent"
    companion_pass_available: bool = True
    sent_at: datetime = Field(default_factory=utc_now)
    accepted_at: datetime | None = None
    declined_at: datetime | None = None


class Circle(SQLModel, table=True):
    id: str = Field(primary_key=True)
    activity_id: str = Field(index=True)
    status: str = "forming"
    compatibility_signals: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class CircleMember(SQLModel, table=True):
    id: str = Field(primary_key=True)
    circle_id: str = Field(index=True)
    resident_id: str = Field(index=True)
    anonymous_label: str
    reveal_first_name: str
    short_bio: str
    conversation_starter: str
    consent_reveal: bool = True
    checked_in: bool = False


class Feedback(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resident_id: str = Field(index=True)
    activity_id: str = Field(index=True)
    felt_after: str
    would_do_similar_again: str
    preference_adjustment: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Proposal(SQLModel, table=True):
    id: str = Field(primary_key=True)
    activity_id: str = Field(index=True)
    title: str
    status: str = "proposed"
    generated_summary: str
    human_approval_status: str = "pending_human_approval"
    ranking_score: float = 0.0
    alternative_notes: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=utc_now)


class AuditItem(SQLModel, table=True):
    id: str = Field(primary_key=True)
    activity_id: str = Field(index=True)
    label: str
    status: str
    detail: str
