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
    preferred_language: str = "English"
    approx_location: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    location_radius_km: int = 5
    interests: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    activity_preferences: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    availability: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    social_comfort: str = "small_group_low_pressure"
    preferred_group_size: dict[str, int] = Field(default_factory=dict, sa_column=Column(JSON))
    accessibility_needs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cost_sensitivity: str = "free_or_low_cost"
    avoid: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    profile_visibility: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "active"
    preferences_extra: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    checked_in_activity_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Professional(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    role: str
    organization: str
    verification_status: str = "approved"
    city: str
    email: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class ConsentRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resident_id: str = Field(index=True)
    professional_id: str = Field(index=True)
    consent_scope: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    revoked_at: datetime | None = None


class Activity(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    type: str
    location: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    start_time: datetime
    end_time: datetime
    capacity: int = 6
    host_id: str | None = None
    cost: float = 0
    accessibility: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    risk_level: str = "low"
    approval_status: str = "generated"
    lifecycle_status: str = "generated"
    proposal_reason_code: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Circle(SQLModel, table=True):
    id: str = Field(primary_key=True)
    activity_id: str = Field(index=True)
    participant_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    shared_signals: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    fit_score: float = 0.0
    status: str = "generated"
    created_at: datetime = Field(default_factory=utc_now)


class Invitation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resident_id: str = Field(index=True)
    activity_id: str = Field(index=True)
    status: str = "sent"
    sent_at: datetime = Field(default_factory=utc_now)
    accepted_at: datetime | None = None
    declined_at: datetime | None = None
    companion_pass_used: bool = False
    companion_guest_name: str | None = None


class Feedback(SQLModel, table=True):
    id: str = Field(primary_key=True)
    resident_id: str = Field(index=True)
    activity_id: str = Field(index=True)
    attended: bool
    felt_after: str
    activity_fit: str
    group_comfort: str
    would_repeat: bool
    safety_report: bool = False
    report_type: str | None = None
    escalation_level: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ConnectionRequest(SQLModel, table=True):
    id: str = Field(primary_key=True)
    from_resident_id: str = Field(index=True)
    to_resident_id: str = Field(index=True)
    activity_id: str = Field(index=True)
    status: str = "requested"
    created_at: datetime = Field(default_factory=utc_now)


class DecisionLog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    endpoint: str = Field(index=True)
    actor_role: str
    actor_id: str
    input_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
