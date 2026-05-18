from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import schemas
from app.api.converters import consent_to_response
from app.api.deps import get_connection
from app.repositories import ConsentRepository

router = APIRouter(prefix="/api/consents", tags=["consents"])


@router.get("/{consent_id}", response_model=schemas.ConsentResponse)
def get_consent(
    consent_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ConsentResponse:
    repo = ConsentRepository(conn)
    consent = repo.get_consent(consent_id)
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")
    return consent_to_response(consent, repo.list_scopes(consent_id))


@router.post("/{consent_id}/revoke", response_model=schemas.ConsentResponse)
def revoke_consent(
    consent_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ConsentResponse:
    repo = ConsentRepository(conn)
    consent = repo.get_consent(consent_id)
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")
    repo.revoke_consent(consent_id)
    conn.commit()
    updated = repo.get_consent(consent_id)
    assert updated is not None
    return consent_to_response(updated, repo.list_scopes(consent_id))
