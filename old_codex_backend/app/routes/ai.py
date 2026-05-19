from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.matching import explain_match, score_activity
from app.models import Activity, Circle, Feedback, Proposal, Resident
from app.routes.common import activity_circle, circle_members, feedback_for_residents

router = APIRouter(prefix="/api/ai", tags=["ai"])


class RankActivitiesIn(BaseModel):
    resident_ids: list[str] | None = None
    activity_ids: list[str] | None = None
    circle_id: str = "circle_photo_walk"


class ExplainMatchIn(BaseModel):
    resident_ids: list[str] | None = None
    activity_id: str = "activity_calm_photo_walk"
    circle_id: str = "circle_photo_walk"


def _residents_from_payload(session: Session, resident_ids: list[str] | None, circle_id: str) -> list[Resident]:
    if resident_ids:
        return session.exec(select(Resident).where(Resident.id.in_(resident_ids))).all()
    members = circle_members(session, circle_id)
    ids = [member.resident_id for member in members]
    return session.exec(select(Resident).where(Resident.id.in_(ids))).all()


@router.post("/rank-activities")
def rank_activities(payload: RankActivitiesIn, session: Session = Depends(get_session)) -> dict:
    residents = _residents_from_payload(session, payload.resident_ids, payload.circle_id)
    feedback = feedback_for_residents(session, residents)
    if payload.activity_ids:
        activities = session.exec(select(Activity).where(Activity.id.in_(payload.activity_ids))).all()
    else:
        activities = session.exec(select(Activity)).all()
    ranked = sorted(
        [score_activity(activity, residents, feedback) for activity in activities],
        key=lambda item: item.score,
        reverse=True,
    )
    return {
        "ranked_activities": [
            {
                "activity_id": item.activity.id,
                "title": item.activity.title,
                "score": item.score,
                "component_scores": item.component_scores,
                "hard_constraints_passed": item.hard_constraints_passed,
                "hard_constraints_failed": item.hard_constraints_failed,
                "reasons_ranked_lower": item.reasons_ranked_lower,
            }
            for item in ranked
        ],
        "weights": {
            "interest_overlap": 25,
            "availability_overlap": 20,
            "distance_travel_radius": 15,
            "social_comfort": 15,
            "intensity_fit": 10,
            "feedback_fit": 10,
            "group_balance": 5,
        },
    }


@router.post("/explain-match")
def explain(payload: ExplainMatchIn, session: Session = Depends(get_session)) -> dict:
    circle = activity_circle(session, payload.activity_id)
    residents = _residents_from_payload(session, payload.resident_ids, circle.id)
    feedback = session.exec(select(Feedback).where(Feedback.resident_id.in_([resident.id for resident in residents]))).all()
    activities = session.exec(select(Activity)).all()
    ranked = sorted(
        [score_activity(activity, residents, feedback) for activity in activities],
        key=lambda item: (item.activity.id == payload.activity_id, item.score),
        reverse=True,
    )
    selected_first = sorted(
        ranked,
        key=lambda item: 0 if item.activity.id == payload.activity_id else 1,
    )
    proposal = session.exec(select(Proposal).where(Proposal.activity_id == payload.activity_id)).first()
    return explain_match(
        selected_first,
        residents,
        proposal.human_approval_status if proposal else "pending_human_approval",
    )
