"""
Activities + venues + hosts + circles + attendance + feedback.

These are the real-world activity instances and their lifecycle: a
venue and host exist; an activity is created at a venue; a circle is
formed from compatible residents; members are added; residents check
in; feedback is collected post-event.
"""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import schemas
from app.api.converters import (
    activity_to_response,
    attendance_to_response,
    circle_member_to_response,
    circle_to_response,
    feedback_to_response,
    host_to_response,
    venue_to_response,
)
from app.api.deps import get_connection
from app.repositories import ActivityRepository

venues_router = APIRouter(prefix="/api/venues", tags=["venues"])
hosts_router = APIRouter(prefix="/api/hosts", tags=["hosts"])
activities_router = APIRouter(prefix="/api/activities", tags=["activities"])


@venues_router.post(
    "",
    response_model=schemas.VenueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_venue(
    payload: schemas.VenueCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.VenueResponse:
    venue = ActivityRepository(conn).create_venue(
        name=payload.name,
        address=payload.address,
        city=payload.city,
        lat=payload.lat,
        lng=payload.lng,
    )
    conn.commit()
    return venue_to_response(venue)


@hosts_router.post(
    "",
    response_model=schemas.HostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_host(
    payload: schemas.HostCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.HostResponse:
    host = ActivityRepository(conn).create_host(
        full_name=payload.full_name,
        host_type=payload.host_type,
        contact_email=payload.contact_email,
    )
    conn.commit()
    return host_to_response(host)


@activities_router.post(
    "",
    response_model=schemas.ActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    payload: schemas.ActivityCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ActivityResponse:
    activity = ActivityRepository(conn).create_activity(
        title=payload.title,
        activity_type=payload.activity_type,
        venue_id=payload.venue_id,
        start_at=payload.start_at.isoformat(),
        end_at=payload.end_at.isoformat(),
        capacity=payload.capacity,
        risk_level=payload.risk_level,
        approval_status=payload.approval_status,
        host_id=payload.host_id,
        cost_cents=payload.cost_cents,
    )
    conn.commit()
    return activity_to_response(activity)


@activities_router.get("/{activity_id}", response_model=schemas.ActivityResponse)
def get_activity(
    activity_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ActivityResponse:
    activity = ActivityRepository(conn).get_activity(activity_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity_to_response(activity)


@activities_router.post(
    "/{activity_id}/circles",
    response_model=schemas.CircleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_circle(
    activity_id: str,
    payload: schemas.CircleCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.CircleResponse:
    repo = ActivityRepository(conn)
    if repo.get_activity(activity_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    circle = repo.create_circle(
        activity_id=activity_id,
        status=payload.status,
        fit_score=payload.fit_score,
        shared_signals_json=payload.shared_signals_json,
    )
    conn.commit()
    return circle_to_response(circle)


circles_router = APIRouter(prefix="/api/circles", tags=["circles"])


@circles_router.post(
    "/{circle_id}/members",
    response_model=schemas.CircleMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_circle_member(
    circle_id: str,
    payload: schemas.CircleMemberCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.CircleMemberResponse:
    member = ActivityRepository(conn).add_circle_member(
        circle_id=circle_id,
        resident_id=payload.resident_id,
    )
    conn.commit()
    return circle_member_to_response(member)


@activities_router.post(
    "/{activity_id}/attendance",
    response_model=schemas.AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_attendance(
    activity_id: str,
    payload: schemas.AttendanceRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.AttendanceResponse:
    repo = ActivityRepository(conn)
    if repo.get_activity(activity_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    event = repo.record_attendance(
        activity_id=activity_id,
        resident_id=payload.resident_id,
        attendance_status=payload.attendance_status,
        check_in_at=payload.check_in_at.isoformat() if payload.check_in_at else None,
        check_out_at=payload.check_out_at.isoformat() if payload.check_out_at else None,
    )
    conn.commit()
    return attendance_to_response(event)


@activities_router.post(
    "/{activity_id}/feedback",
    response_model=schemas.FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    activity_id: str,
    payload: schemas.FeedbackRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.FeedbackResponse:
    repo = ActivityRepository(conn)
    if repo.get_activity(activity_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    feedback = repo.add_feedback(
        activity_id=activity_id,
        resident_id=payload.resident_id,
        felt_after=payload.felt_after,
        activity_fit=payload.activity_fit,
        group_comfort=payload.group_comfort,
        would_repeat=payload.would_repeat,
        safety_reported=payload.safety_reported,
        notes=payload.notes,
    )
    conn.commit()
    return feedback_to_response(feedback)
