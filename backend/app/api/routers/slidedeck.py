"""
Slide deck router.

Serves the standalone pitch deck HTML file from ``frontend-jose/``
at ``/slidedeck`` (and ``/slidedeck/``) so reviewers can open the deck
straight from the running API without launching a separate static
server.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["slidedeck"])

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SLIDEDECK_PATH = _REPO_ROOT / "frontend-jose" / "CivicCircles Pitch.html"


@router.get("/slidedeck", include_in_schema=False)
@router.get("/slidedeck/", include_in_schema=False)
def get_slidedeck() -> FileResponse:
    if not _SLIDEDECK_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Slide deck not found at {_SLIDEDECK_PATH}",
        )
    return FileResponse(
        path=_SLIDEDECK_PATH,
        media_type="text/html; charset=utf-8",
        filename="CivicCircles-Pitch.html",
    )
