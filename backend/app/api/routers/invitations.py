from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import schemas
from app.api.converters import invitation_to_response
from app.api.deps import get_connection
from app.repositories import ActivityRepository


def _fetch_invitation(conn: Connection, invitation_id: str):
    row = conn.execute(
        "SELECT * FROM invitations WHERE id = ?", (invitation_id,)
    ).fetchone()
    return row


def _row_to_invitation_response(row) -> schemas.InvitationResponse:
    from datetime import datetime

    def _opt(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    return schemas.InvitationResponse(
        id=row["id"],
        circle_id=row["circle_id"],
        activity_id=row["activity_id"],
        resident_id=row["resident_id"],
        status=row["status"],
        companion_pass_used=bool(row["companion_pass_used"]),
        sent_at=datetime.fromisoformat(row["sent_at"]),
        responded_at=_opt(row["responded_at"]),
    )


router = APIRouter(prefix="/api/invitations", tags=["invitations"])


@router.post(
    "",
    response_model=schemas.InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: schemas.InvitationCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.InvitationResponse:
    invitation = ActivityRepository(conn).create_invitation(
        circle_id=payload.circle_id,
        activity_id=payload.activity_id,
        resident_id=payload.resident_id,
        status=payload.status,
    )
    conn.commit()
    return invitation_to_response(invitation)


@router.get("/{invitation_id}", response_model=schemas.InvitationResponse)
def get_invitation(
    invitation_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.InvitationResponse:
    row = _fetch_invitation(conn, invitation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return _row_to_invitation_response(row)


@router.post("/{invitation_id}/accept", response_model=schemas.InvitationResponse)
def accept_invitation(
    invitation_id: str,
    payload: schemas.InvitationDecisionRequest | None = None,
    conn: Connection = Depends(get_connection),
) -> schemas.InvitationResponse:
    row = _fetch_invitation(conn, invitation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    repo = ActivityRepository(conn)
    repo.update_invitation_status(
        invitation_id=invitation_id,
        status="accepted",
        companion_pass_used=(payload.companion_pass_used if payload else None),
    )
    conn.commit()
    return _row_to_invitation_response(_fetch_invitation(conn, invitation_id))


@router.post("/{invitation_id}/decline", response_model=schemas.InvitationResponse)
def decline_invitation(
    invitation_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.InvitationResponse:
    row = _fetch_invitation(conn, invitation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    ActivityRepository(conn).update_invitation_status(
        invitation_id=invitation_id,
        status="declined",
    )
    conn.commit()
    return _row_to_invitation_response(_fetch_invitation(conn, invitation_id))
