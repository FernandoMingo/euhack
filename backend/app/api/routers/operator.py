"""
Operator-only routes: matching runs + peer ratings.

These are intentionally namespaced under /api/operator to make it clear
in the URL that they are not resident-facing. Peer ratings in particular
must never surface to other residents — see AGENTS.md privacy guardrails.
"""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import schemas
from app.api.converters import (
    match_candidate_to_response,
    matching_run_to_response,
    peer_flag_to_response,
    peer_rating_to_response,
    peer_rollup_to_response,
)
from app.api.deps import get_connection
from app.repositories import MatchingRepository, RatingRepository

router = APIRouter(prefix="/api/operator", tags=["operator"])


# ---------- Matching runs ----------


@router.post(
    "/matching-runs",
    response_model=schemas.MatchingRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_matching_run(
    payload: schemas.MatchingRunCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.MatchingRunResponse:
    run = MatchingRepository(conn).create_matching_run(
        run_type=payload.run_type,
        model_version=payload.model_version,
        score_algorithm=payload.score_algorithm,
        source_window_start=payload.source_window_start.isoformat() if payload.source_window_start else None,
        source_window_end=payload.source_window_end.isoformat() if payload.source_window_end else None,
    )
    conn.commit()
    return matching_run_to_response(run)


@router.post(
    "/matching-runs/{matching_run_id}/candidates",
    response_model=schemas.MatchCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_match_candidate(
    matching_run_id: str,
    payload: schemas.MatchCandidateCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.MatchCandidateResponse:
    candidate = MatchingRepository(conn).add_match_candidate(
        matching_run_id=matching_run_id,
        total_score=payload.total_score,
        rank_position=payload.rank_position,
        hard_constraints_passed=payload.hard_constraints_passed,
        resident_id=payload.resident_id,
        circle_id=payload.circle_id,
        activity_id=payload.activity_id,
    )
    conn.commit()
    return match_candidate_to_response(candidate)


@router.get(
    "/matching-runs/{matching_run_id}/candidates",
    response_model=list[schemas.MatchCandidateResponse],
)
def list_top_candidates(
    matching_run_id: str,
    limit: int = Query(default=5, ge=1, le=100),
    conn: Connection = Depends(get_connection),
) -> list[schemas.MatchCandidateResponse]:
    candidates = MatchingRepository(conn).get_top_candidates(
        matching_run_id=matching_run_id,
        limit=limit,
    )
    return [match_candidate_to_response(c) for c in candidates]


# ---------- Peer ratings ----------


@router.post(
    "/peer-ratings",
    response_model=schemas.PeerRatingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_peer_rating(
    payload: schemas.PeerRatingCreateRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.PeerRatingResponse:
    if payload.rater_resident_id == payload.ratee_resident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rater and ratee must differ",
        )
    rating = RatingRepository(conn).create_peer_rating(
        activity_id=payload.activity_id,
        rater_resident_id=payload.rater_resident_id,
        ratee_resident_id=payload.ratee_resident_id,
        comfort_to_be_with=payload.comfort_to_be_with,
        respectful_behavior=payload.respectful_behavior,
        reliability_showed_up=payload.reliability_showed_up,
        group_contribution=payload.group_contribution,
        note_text=payload.note_text,
    )
    conn.commit()
    return peer_rating_to_response(rating)


@router.get(
    "/peer-ratings/resident/{resident_id}",
    response_model=list[schemas.PeerRatingResponse],
)
def list_peer_ratings_for_resident(
    resident_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection = Depends(get_connection),
) -> list[schemas.PeerRatingResponse]:
    ratings = RatingRepository(conn).list_ratings_for_resident(
        resident_id=resident_id,
        limit=limit,
    )
    return [peer_rating_to_response(r) for r in ratings]


@router.post(
    "/peer-rollups",
    response_model=schemas.PeerRatingRollupResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_peer_rollup(
    payload: schemas.PeerRatingRollupRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.PeerRatingRollupResponse:
    rollup = RatingRepository(conn).upsert_peer_rollup(
        resident_id=payload.resident_id,
        model_version=payload.model_version,
        comfort_to_be_with_score=payload.comfort_to_be_with_score,
        respectful_behavior_score=payload.respectful_behavior_score,
        reliability_showed_up_score=payload.reliability_showed_up_score,
        group_contribution_score=payload.group_contribution_score,
        rating_count=payload.rating_count,
        confidence=payload.confidence,
        recentness_weighted_score=payload.recentness_weighted_score,
    )
    conn.commit()
    return peer_rollup_to_response(rollup)


@router.post(
    "/peer-ratings/{peer_rating_id}/flag",
    response_model=schemas.PeerRatingFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
def flag_peer_rating(
    peer_rating_id: str,
    payload: schemas.PeerRatingFlagRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.PeerRatingFlagResponse:
    flag = RatingRepository(conn).flag_peer_rating(
        peer_rating_id=peer_rating_id,
        flag_type=payload.flag_type,
        severity=payload.severity,
        details=payload.details,
    )
    conn.commit()
    return peer_flag_to_response(flag)
