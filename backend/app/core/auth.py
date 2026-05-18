from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status


@dataclass
class Actor:
    role: str
    actor_id: str


def get_actor(
    x_actor_role: str | None = Header(default=None),
    x_actor_id: str | None = Header(default=None),
) -> Actor:
    if not x_actor_role or not x_actor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing mock actor headers. Provide x-actor-role and x-actor-id.",
        )
    return Actor(role=x_actor_role, actor_id=x_actor_id)


def require_role(expected_role: str):
    def dependency(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.role != expected_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role={expected_role}",
            )
        return actor

    return dependency
