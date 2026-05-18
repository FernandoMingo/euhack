"""
Operator-only routes: matching runs + peer ratings.

These are intentionally namespaced under /api/operator to make it clear
in the URL that they are not resident-facing. Peer ratings in particular
must never surface to other residents — see AGENTS.md privacy guardrails.
"""

from __future__ import annotations

import json
from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api import schemas
from app.api.converters import (
    activity_plan_to_response,
    audit_event_to_response,
    circle_to_response,
    invitation_to_response,
    match_candidate_to_response,
    matching_run_to_response,
    peer_flag_to_response,
    peer_rating_to_response,
    peer_rollup_to_response,
)
from app.api.deps import get_connection, get_llm_client
from app.repositories import ActivityRepository, MatchingRepository, RatingRepository
from app.repositories.base import parse_dt
from app.services import (
    ActivityPlanningService,
    LLMClient,
    LLMConfigurationError,
    LLMResponseError,
    MatchingWorkflowService,
    PromptSafetyError,
)

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


@router.post(
    "/referrals/{referral_id}/matching-workflow",
    response_model=schemas.MatchingWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_referral_matching_workflow(
    referral_id: str,
    payload: schemas.MatchingWorkflowRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.MatchingWorkflowResponse:
    try:
        result = MatchingWorkflowService(conn).accept_referral_and_propose_matches(
            referral_id=referral_id,
            top_n_activities=payload.top_n_activities,
            top_n_groups=payload.top_n_groups,
            min_group_size=payload.min_group_size,
            max_group_size=payload.max_group_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    grouping = result.grouping_result
    return schemas.MatchingWorkflowResponse(
        referral_id=result.referral_id,
        activity_ranking_run_id=result.activity_ranking_run_id,
        top_activity_results=[
            schemas.MatchResultSummaryResponse(
                template_id=item.template.id,
                template_code=item.template.code,
                template_title=item.template.title,
                total_score=item.breakdown.total,
                cosine=item.breakdown.cosine,
                rank_position=item.candidate.rank_position,
                explanation_summary=item.explanation.summary_text,
            )
            for item in result.top_activity_results
        ],
        circle_matching_run_id=grouping.matching_run_id if grouping is not None else None,
        proposed_groups=[
            schemas.ProposedGroupReviewResponse(
                circle=circle_to_response(group.circle) if group.circle is not None else None,
                member_ids=[member.id for member in group.members],
                fit_score=group.fit_score,
                shared_availability=list(group.shared_availability),
                shared_interests=list(group.shared_interests),
                summary_text=group.summary_text,
                payload=group.payload,
            )
            for group in (grouping.groups if grouping is not None else ())
        ],
        unmatched_residents=[
            schemas.UnmatchedResidentReviewResponse(
                resident_id=item.resident.id,
                first_name=item.resident.first_name,
                reason=item.reason,
                summary_text=item.summary_text,
                payload=item.payload,
            )
            for item in (grouping.unmatched if grouping is not None else ())
        ],
    )


@router.post(
    "/activities/{activity_id}/decisions",
    response_model=schemas.OperatorDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_operator_decision(
    activity_id: str,
    payload: schemas.OperatorDecisionRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.OperatorDecisionResponse:
    try:
        MatchingWorkflowService(conn).record_operator_decision(
            activity_id=activity_id,
            operator_id=payload.operator_id,
            decision=payload.decision,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.OperatorDecisionResponse(
        activity_id=activity_id,
        operator_id=payload.operator_id,
        decision=payload.decision,
        reason=payload.reason,
    )


# ---------- Activity planning (LLM-backed) ----------


@router.post(
    "/circles/{circle_id}/activity-plan",
    response_model=schemas.ActivityPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_activity_plan(
    circle_id: str,
    payload: schemas.ActivityPlanRequest,
    conn: Connection = Depends(get_connection),
    llm_client: LLMClient | None = Depends(get_llm_client),
) -> schemas.ActivityPlanResponse:
    """Generate an operator-reviewable plan for a proposed circle.

    The plan is persisted as a draft, then the LLM call is made. Whether
    the call succeeds or fails, the row stays auditable. The plan does
    not create an `activities` row or send invitations on its own.
    """
    if llm_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Activity-planning LLM client is not configured. "
                "Set OPENAI_API_KEY and inject OpenAIChatLLMClient into "
                "create_app(...)."
            ),
        )
    service = ActivityPlanningService(conn, llm_client=llm_client)
    try:
        result = service.generate_plan_for_circle(
            circle_id=circle_id,
            operator_constraints=payload.operator_constraints,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PromptSafetyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return activity_plan_to_response(result.plan)


@router.get(
    "/activity-plans/{plan_id}",
    response_model=schemas.ActivityPlanResponse,
)
def get_activity_plan(
    plan_id: str,
    conn: Connection = Depends(get_connection),
) -> schemas.ActivityPlanResponse:
    plan = ActivityPlanningService(conn).get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity plan {plan_id} not found",
        )
    return activity_plan_to_response(plan)


@router.get(
    "/circles/{circle_id}/activity-plans",
    response_model=list[schemas.ActivityPlanResponse],
)
def list_activity_plans_for_circle(
    circle_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    conn: Connection = Depends(get_connection),
) -> list[schemas.ActivityPlanResponse]:
    plans = ActivityPlanningService(conn).list_plans_for_circle(
        circle_id=circle_id, limit=limit
    )
    return [activity_plan_to_response(plan) for plan in plans]


@router.post(
    "/activity-plans/{plan_id}/decision",
    response_model=schemas.ActivityPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_activity_plan_decision(
    plan_id: str,
    payload: schemas.ActivityPlanDecisionRequest,
    conn: Connection = Depends(get_connection),
) -> schemas.ActivityPlanResponse:
    service = ActivityPlanningService(conn)
    try:
        plan = service.record_operator_decision(
            plan_id=plan_id,
            operator_id=payload.operator_id,
            decision=payload.decision,
            reason=payload.reason,
            edits=payload.edits,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return activity_plan_to_response(plan)


@router.post(
    "/circles/{circle_id}/send-invitations",
    response_model=schemas.InvitationPromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_invitations_for_circle(
    circle_id: str,
    actor_id: str | None = None,
    conn: Connection = Depends(get_connection),
) -> schemas.InvitationPromotionResponse:
    try:
        invitations = MatchingWorkflowService(conn).send_invitations_for_approved_circle(
            circle_id=circle_id,
            actor_id=actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.InvitationPromotionResponse(
        circle_id=circle_id,
        invitations=[invitation_to_response(invitation) for invitation in invitations],
    )


def _json_object(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


@router.get(
    "/proposed-circles",
    response_model=schemas.ProposedCirclesResponse,
)
def list_proposed_circles(
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection = Depends(get_connection),
) -> schemas.ProposedCirclesResponse:
    activities = ActivityRepository(conn)
    circles = activities.list_circles(status="proposed", limit=limit)
    return schemas.ProposedCirclesResponse(
        circles=[
            schemas.ProposedCircleDashboardResponse(
                circle=circle_to_response(circle),
                member_ids=[
                    member.resident_id
                    for member in activities.list_circle_members(circle_id=circle.id)
                ],
                shared_signals=_json_object(circle.shared_signals_json),
            )
            for circle in circles
        ]
    )


@router.get(
    "/matching-runs/{matching_run_id}/review",
    response_model=schemas.MatchingRunReviewResponse,
)
def get_matching_run_review(
    matching_run_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection = Depends(get_connection),
) -> schemas.MatchingRunReviewResponse:
    rows = MatchingRepository(conn).list_candidate_review_rows(
        matching_run_id=matching_run_id,
        limit=limit,
    )
    return schemas.MatchingRunReviewResponse(
        matching_run_id=matching_run_id,
        candidates=[
            schemas.MatchCandidateReviewResponse(
                candidate_id=row["candidate_id"],
                matching_run_id=row["matching_run_id"],
                resident_id=row["resident_id"],
                circle_id=row["circle_id"],
                activity_id=row["activity_id"],
                total_score=row["total_score"],
                rank_position=row["rank_position"],
                hard_constraints_passed=bool(row["hard_constraints_passed"]),
                summary_text=row["summary_text"],
                explanation=_json_object(row["explanation_json"])
                if row["explanation_json"] is not None
                else None,
                created_at=parse_dt(row["candidate_created_at"]),  # type: ignore[arg-type]
            )
            for row in rows
        ],
    )


@router.get(
    "/audit-events",
    response_model=list[schemas.AuditEventResponse],
)
def list_audit_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    conn: Connection = Depends(get_connection),
) -> list[schemas.AuditEventResponse]:
    events = ActivityRepository(conn).list_audit_events(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return [audit_event_to_response(event) for event in events]


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
