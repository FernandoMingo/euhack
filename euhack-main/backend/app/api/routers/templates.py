from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import schemas
from app.api.converters import template_to_response
from app.api.deps import get_connection
from app.repositories import ActivityTemplateRepository

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[schemas.ActivityTemplateResponse])
def list_templates(
    family: str | None = Query(default=None),
    conn: Connection = Depends(get_connection),
) -> list[schemas.ActivityTemplateResponse]:
    repo = ActivityTemplateRepository(conn)
    templates = repo.list_templates(family=family)
    return [template_to_response(t, repo.get_tags(t.id)) for t in templates]


@router.get("/families", response_model=list[str])
def list_families(
    conn: Connection = Depends(get_connection),
) -> list[str]:
    return ActivityTemplateRepository(conn).list_families()


@router.get("/by-tag/{tag}", response_model=list[schemas.ActivityTemplateResponse])
def search_by_tag(
    tag: str,
    conn: Connection = Depends(get_connection),
) -> list[schemas.ActivityTemplateResponse]:
    repo = ActivityTemplateRepository(conn)
    templates = repo.search_by_tag(tag)
    return [template_to_response(t, repo.get_tags(t.id)) for t in templates]


@router.get("/{code}", response_model=schemas.ActivityTemplateResponse)
def get_template(
    code: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ActivityTemplateResponse:
    repo = ActivityTemplateRepository(conn)
    template = repo.get_template_by_code(code)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template_to_response(template, repo.get_tags(template.id))
