"""Resident-facing invitation inbox endpoints.

These are intentionally thin: they validate ownership (the inbox item
must belong to the resident in the path) and delegate to the
`InvitationInboxService`. They never expose fit scores, peer ratings,
or other residents' data.
"""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import schemas
from app.api.converters import inbox_item_to_response
from app.api.deps import get_connection
from app.repositories import ResidentInboxRepository, ResidentRepository
from app.services import InvitationInboxService


router = APIRouter(prefix="/api/residents", tags=["inbox"])


def _ensure_resident_exists(conn: Connection, resident_id: str) -> None:
    if ResidentRepository(conn).get_resident(resident_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found"
        )


def _fetch_owned_item(
    conn: Connection, *, resident_id: str, item_id: str
):
    item = ResidentInboxRepository(conn).get_item(item_id)
    if item is None or item.resident_id != resident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inbox item not found"
        )
    return item


@router.get(
    "/{resident_id}/inbox",
    response_model=list[schemas.ResidentInboxItemResponse],
)
def list_inbox(
    resident_id: str,
    status_filter: schemas.InboxItemStatusLiteral | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_connection),
) -> list[schemas.ResidentInboxItemResponse]:
    _ensure_resident_exists(conn, resident_id)
    items = ResidentInboxRepository(conn).list_for_resident(
        resident_id=resident_id, status=status_filter, limit=limit
    )
    return [inbox_item_to_response(item) for item in items]


@router.get(
    "/{resident_id}/inbox/{item_id}",
    response_model=schemas.ResidentInboxItemResponse,
)
def get_inbox_item(
    resident_id: str,
    item_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentInboxItemResponse:
    _ensure_resident_exists(conn, resident_id)
    item = _fetch_owned_item(conn, resident_id=resident_id, item_id=item_id)
    return inbox_item_to_response(item)


@router.post(
    "/{resident_id}/inbox/{item_id}/read",
    response_model=schemas.ResidentInboxItemResponse,
)
def mark_inbox_item_read(
    resident_id: str,
    item_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentInboxItemResponse:
    _ensure_resident_exists(conn, resident_id)
    _fetch_owned_item(conn, resident_id=resident_id, item_id=item_id)
    item = InvitationInboxService(conn).mark_inbox_item_read(item_id=item_id)
    conn.commit()
    return inbox_item_to_response(item)


@router.post(
    "/{resident_id}/inbox/{item_id}/archive",
    response_model=schemas.ResidentInboxItemResponse,
)
def archive_inbox_item(
    resident_id: str,
    item_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ResidentInboxItemResponse:
    _ensure_resident_exists(conn, resident_id)
    _fetch_owned_item(conn, resident_id=resident_id, item_id=item_id)
    item = InvitationInboxService(conn).archive_inbox_item(item_id=item_id)
    conn.commit()
    return inbox_item_to_response(item)
