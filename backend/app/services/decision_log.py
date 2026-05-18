from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session

from app.core.auth import Actor
from app.models import DecisionLog


def write_decision_log(
    session: Session,
    *,
    endpoint: str,
    actor: Actor,
    input_summary: dict,
    output_summary: dict,
) -> None:
    record = DecisionLog(
        id=f"dlog_{uuid4().hex[:12]}",
        endpoint=endpoint,
        actor_role=actor.role,
        actor_id=actor.actor_id,
        input_summary=input_summary,
        output_summary=output_summary,
    )
    session.add(record)
    session.commit()
