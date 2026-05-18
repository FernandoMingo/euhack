from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.core.auth import Actor, require_role
from app.core.response import ok_response
from app.db import get_session
from app.models import Activity, Circle, ConsentRecord, Feedback, Resident
from app.schemas import ExplainMatchIn, GenerateCirclesIn, RankActivitiesIn, UpdatePreferencesFromFeedbackIn
from app.services.decision_log import write_decision_log
from app.services.matching import build_explanation, score_activity
from app.services.policy import has_active_matching_consent

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _select_residents(session: Session, resident_ids: list[str] | None) -> list[Resident]:
    if resident_ids:
        residents = session.exec(select(Resident).where(Resident.id.in_(resident_ids))).all()
    else:
        residents = session.exec(select(Resident)).all()
    return residents


def _ensure_matching_consent(session: Session, residents: list[Resident]) -> None:
    for resident in residents:
        records = session.exec(select(ConsentRecord).where(ConsentRecord.resident_id == resident.id)).all()
        if not has_active_matching_consent(records):
            raise HTTPException(status_code=403, detail=f"Resident {resident.id} has no active matching consent")


def _feedback_lookup(session: Session, residents: list[Resident]) -> dict[str, list[Feedback]]:
    feedback_items = session.exec(select(Feedback).where(Feedback.resident_id.in_([r.id for r in residents]))).all()
    lookup: dict[str, list[Feedback]] = {}
    for item in feedback_items:
        lookup.setdefault(item.resident_id, []).append(item)
    return lookup


@router.post("/generate-circles")
def generate_circles(
    payload: GenerateCirclesIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    residents = _select_residents(session, payload.resident_ids)
    if len(residents) < 3:
        raise HTTPException(status_code=400, detail="Need at least three residents to generate a circle")
    _ensure_matching_consent(session, residents)
    activities = session.exec(select(Activity)).all()
    if not activities:
        raise HTTPException(status_code=400, detail="No activities available")
    feedback_lookup = _feedback_lookup(session, residents)
    ranked = sorted(
        [score_activity(activity=activity, residents=residents[:5], feedback_by_resident=feedback_lookup) for activity in activities],
        key=lambda item: item.fit_score,
        reverse=True,
    )
    top = ranked[0]
    circle_id = f"circle_{top.activity.id.replace('activity_', '')}"
    circle = Circle(
        id=circle_id,
        activity_id=top.activity.id,
        participant_ids=[r.id for r in residents[:5]],
        shared_signals=["small_group", "calm", "community"],
        fit_score=top.fit_score,
        status="generated",
    )
    session.merge(circle)
    session.commit()
    output = {
        "circle_id": circle.id,
        "activity_id": top.activity.id,
        "participant_ids": circle.participant_ids,
        "fit_score": top.fit_score,
    }
    write_decision_log(
        session,
        endpoint="generate-circles",
        actor=actor,
        input_summary={"resident_ids": [r.id for r in residents[:5]]},
        output_summary=output,
    )
    return ok_response(output, request)


@router.post("/rank-activities")
def rank_activities(
    payload: RankActivitiesIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    residents = _select_residents(session, payload.resident_ids)
    _ensure_matching_consent(session, residents)
    activities = (
        session.exec(select(Activity).where(Activity.id.in_(payload.activity_ids))).all()
        if payload.activity_ids
        else session.exec(select(Activity)).all()
    )
    feedback_lookup = _feedback_lookup(session, residents)
    scored = [
        score_activity(activity=activity, residents=residents, feedback_by_resident=feedback_lookup) for activity in activities
    ]
    ranked = sorted(scored, key=lambda item: item.fit_score, reverse=True)
    output = [
        {
            "activity_id": item.activity.id,
            "fit_score": item.fit_score,
            "component_scores": item.component_scores,
            "hard_constraints_passed": item.hard_constraints_passed,
            "hard_constraints_failed": item.hard_constraints_failed,
        }
        for item in ranked
    ]
    write_decision_log(
        session,
        endpoint="rank-activities",
        actor=actor,
        input_summary={"resident_ids": payload.resident_ids, "activity_count": len(activities)},
        output_summary={"top_activity_id": output[0]["activity_id"] if output else None},
    )
    return ok_response({"ranked_activities": output}, request)


@router.post("/generate-activity-proposal")
def generate_activity_proposal(
    payload: RankActivitiesIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    residents = _select_residents(session, payload.resident_ids)
    _ensure_matching_consent(session, residents)
    activities = (
        session.exec(select(Activity).where(Activity.id.in_(payload.activity_ids))).all()
        if payload.activity_ids
        else session.exec(select(Activity)).all()
    )
    feedback_lookup = _feedback_lookup(session, residents)
    scored = sorted(
        [score_activity(activity=activity, residents=residents, feedback_by_resident=feedback_lookup) for activity in activities],
        key=lambda item: item.fit_score,
        reverse=True,
    )
    if not scored:
        raise HTTPException(status_code=400, detail="No activities to propose")
    top = scored[0]
    proposal = session.get(Activity, top.activity.id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Top activity not found")
    proposal.approval_status = "pending_approval"
    proposal.lifecycle_status = "pending_approval"
    session.add(proposal)
    session.commit()
    output = {
        "proposal_id": proposal.id,
        "status": proposal.approval_status,
        "fit_score": top.fit_score,
        "component_scores": top.component_scores,
    }
    write_decision_log(
        session,
        endpoint="generate-activity-proposal",
        actor=actor,
        input_summary={"resident_ids": payload.resident_ids},
        output_summary={"proposal_id": proposal.id, "status": proposal.approval_status},
    )
    return ok_response(output, request)


@router.post("/explain-match")
def explain_match(
    payload: ExplainMatchIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    residents = _select_residents(session, payload.resident_ids)
    _ensure_matching_consent(session, residents)
    activity = session.get(Activity, payload.activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    feedback_lookup = _feedback_lookup(session, residents)
    primary = score_activity(activity=activity, residents=residents, feedback_by_resident=feedback_lookup)
    alternatives = session.exec(select(Activity).where(Activity.id != payload.activity_id)).all()
    alternative_scored = [
        score_activity(activity=alt, residents=residents, feedback_by_resident=feedback_lookup) for alt in alternatives[:3]
    ]
    explanation = build_explanation(
        primary,
        residents=residents,
        alternatives=alternative_scored,
        approval_status=activity.approval_status,
    )
    write_decision_log(
        session,
        endpoint="explain-match",
        actor=actor,
        input_summary={"resident_ids": payload.resident_ids, "activity_id": payload.activity_id},
        output_summary={"recommended_activity": explanation["recommended_activity"]},
    )
    return ok_response(explanation, request)


@router.post("/update-preferences-from-feedback")
def update_preferences_from_feedback(
    payload: UpdatePreferencesFromFeedbackIn,
    request: Request,
    actor: Actor = Depends(require_role("operator")),
    session: Session = Depends(get_session),
):
    resident = session.get(Resident, payload.resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    feedback = session.exec(select(Feedback).where(Feedback.resident_id == resident.id)).all()
    updates: dict[str, str] = {}
    if any(item.group_comfort == "no" for item in feedback):
        updates["preferred_group_size_max"] = "4"
        resident.preferred_group_size["max"] = 4
    if any(item.activity_fit == "no" for item in feedback):
        updates["activity_intensity"] = "lower"
    if any(item.felt_after == "better" and item.would_repeat for item in feedback):
        updates["repeat_activity_bias"] = "increase"
    session.add(resident)
    session.commit()
    write_decision_log(
        session,
        endpoint="update-preferences-from-feedback",
        actor=actor,
        input_summary={"resident_id": resident.id, "feedback_items": len(feedback)},
        output_summary={"updates": updates},
    )
    return ok_response({"resident_id": resident.id, "updates": updates}, request)
