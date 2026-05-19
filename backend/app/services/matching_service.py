"""Auditable matching workflows composed from repositories and engines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Connection

from app.dataclasses import Invitation
from app.matching import BEHAVIORAL_MODEL_VERSION, CircleEngine, GroupingResult, MatchingEngine, MatchResult
from app.repositories import (
    ActivityRepository,
    ActivityTemplateRepository,
    MatchingRepository,
    ReferralRepository,
    ResidentRepository,
)
from app.repositories.base import new_id, utc_now_iso


@dataclass(slots=True, frozen=True)
class ReferralMatchingWorkflowResult:
    referral_id: str
    activity_ranking_run_id: str
    top_activity_results: tuple[MatchResult, ...]
    grouping_result: GroupingResult | None


class MatchingWorkflowService:
    """Service layer for system/operator matching workflows.

    Routes should stay thin and delegate multi-step state transitions here so
    matching runs, circle proposals, invitations, and audit rows remain in sync.
    """

    def __init__(self, conn: Connection) -> None:
        self.conn = conn
        self.activities = ActivityRepository(conn)
        self.templates = ActivityTemplateRepository(conn)
        self.matching = MatchingRepository(conn)
        self.referrals = ReferralRepository(conn)
        self.residents = ResidentRepository(conn)

    def accept_referral_and_propose_matches(
        self,
        *,
        referral_id: str,
        top_n_activities: int = 5,
        top_n_groups: int = 3,
        min_group_size: int = 3,
        max_group_size: int = 6,
    ) -> ReferralMatchingWorkflowResult:
        referral = self.referrals.get_referral(referral_id)
        if referral is None:
            raise ValueError(f"Referral {referral_id} not found")

        self.referrals.update_status(referral_id=referral_id, status="accepted")
        self._add_audit_event(
            actor_type="system",
            action="referral.accepted",
            entity_type="referral",
            entity_id=referral_id,
            metadata={"resident_id": referral.resident_id},
        )

        ranking_engine = MatchingEngine(
            residents=self.residents,
            templates=self.templates,
            matching=self.matching,
            activities=self.activities,
            model_version=BEHAVIORAL_MODEL_VERSION,
            score_algorithm="cosine_weighted_v2",
        )
        run_id, top_results = ranking_engine.run_matching(
            resident_id=referral.resident_id,
            top_n=top_n_activities,
        )
        self._add_audit_event(
            actor_type="system",
            action="matching.activity_ranking.completed",
            entity_type="matching_run",
            entity_id=run_id,
            metadata={
                "resident_id": referral.resident_id,
                "referral_id": referral_id,
                "top_n": top_n_activities,
            },
        )

        grouping_result: GroupingResult | None = None
        if top_results:
            grouping_engine = CircleEngine(
                residents=self.residents,
                templates=self.templates,
                matching=self.matching,
                activities=self.activities,
                model_version=BEHAVIORAL_MODEL_VERSION,
                score_algorithm="circle_fair_v2",
                fair_grouping=True,
            )
            grouping_result = grouping_engine.run_grouping(
                template_id=top_results[0].template.id,
                top_n=top_n_groups,
                min_group_size=min_group_size,
                max_group_size=max_group_size,
            )
            self._add_audit_event(
                actor_type="system",
                action="matching.circle_matching.completed",
                entity_type="matching_run",
                entity_id=grouping_result.matching_run_id,
                metadata={
                    "referral_id": referral_id,
                    "seed_resident_id": referral.resident_id,
                    "template_code": top_results[0].template.code,
                    "groups": len(grouping_result.groups),
                    "unmatched": len(grouping_result.unmatched),
                },
            )

        self.conn.commit()
        return ReferralMatchingWorkflowResult(
            referral_id=referral_id,
            activity_ranking_run_id=run_id,
            top_activity_results=tuple(top_results),
            grouping_result=grouping_result,
        )

    def record_operator_decision(
        self,
        *,
        activity_id: str,
        operator_id: str,
        decision: str,
        reason: str | None = None,
    ) -> None:
        if self.activities.get_activity(activity_id) is None:
            raise ValueError(f"Activity {activity_id} not found")
        decision_id = new_id("operator_decision")
        now = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO operator_decisions (
                id, activity_id, operator_id, decision, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (decision_id, activity_id, operator_id, decision, reason, now),
        )
        self._add_audit_event(
            actor_type="operator",
            actor_id=operator_id,
            action=f"operator_decision.{decision}",
            entity_type="activity",
            entity_id=activity_id,
            metadata={"reason": reason},
        )
        self.conn.commit()

    def send_invitations_for_approved_circle(
        self,
        *,
        circle_id: str,
        actor_id: str | None = None,
    ) -> tuple[Invitation, ...]:
        circle = self.activities.get_circle(circle_id)
        if circle is None:
            raise ValueError(f"Circle {circle_id} not found")
        if circle.activity_id is None:
            raise ValueError("Circle must be anchored to an approved activity before invitations")
        activity = self.activities.get_activity(circle.activity_id)
        if activity is None or activity.approval_status != "approved":
            raise ValueError("Circle activity must be operator-approved before invitations")

        invitations: list[Invitation] = []
        for member in self.activities.list_circle_members(circle_id=circle_id):
            invitations.append(
                self.activities.create_invitation(
                    circle_id=circle_id,
                    activity_id=circle.activity_id,
                    resident_id=member.resident_id,
                )
            )
            self._add_audit_event(
                actor_type="system",
                actor_id=actor_id,
                action="invitation.sent",
                entity_type="resident",
                entity_id=member.resident_id,
                metadata={"circle_id": circle_id, "activity_id": circle.activity_id},
            )
        self.activities.update_circle_status(circle_id=circle_id, status="invitations_sent")
        self._add_audit_event(
            actor_type="system",
            actor_id=actor_id,
            action="circle.invitations_sent",
            entity_type="circle",
            entity_id=circle_id,
            metadata={"activity_id": circle.activity_id, "count": len(invitations)},
        )
        self.conn.commit()
        return tuple(invitations)

    def _add_audit_event(
        self,
        *,
        actor_type: str,
        action: str,
        entity_type: str,
        metadata: dict[str, object],
        actor_id: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_events (
                id, actor_type, actor_id, action, entity_type, entity_id,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("audit"),
                actor_type,
                actor_id,
                action,
                entity_type,
                entity_id,
                json.dumps(metadata, sort_keys=True),
                utc_now_iso(),
            ),
        )
