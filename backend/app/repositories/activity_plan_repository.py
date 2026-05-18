"""Repository for LLM-generated activity plan drafts.

The `activity_plans` table stores the prompt payload, model metadata and
structured plan JSON produced by the planning service so every plan is
fully auditable. The table is touched only by this repository; the
service layer composes higher-level workflows around it.
"""

from __future__ import annotations

from app.dataclasses import ActivityPlan
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


def _row_to_plan(row: object) -> ActivityPlan:
    return ActivityPlan(
        id=row["id"],  # type: ignore[index]
        circle_id=row["circle_id"],  # type: ignore[index]
        template_id=row["template_id"],  # type: ignore[index]
        activity_id=row["activity_id"],  # type: ignore[index]
        status=row["status"],  # type: ignore[index,arg-type]
        model_provider=row["model_provider"],  # type: ignore[index]
        model_name=row["model_name"],  # type: ignore[index]
        prompt_version=row["prompt_version"],  # type: ignore[index]
        prompt_text=row["prompt_text"],  # type: ignore[index]
        request_payload_json=row["request_payload_json"],  # type: ignore[index]
        response_json=row["response_json"],  # type: ignore[index]
        summary_text=row["summary_text"],  # type: ignore[index]
        requires_review_flags_json=row["requires_review_flags_json"],  # type: ignore[index]
        operator_constraints_json=row["operator_constraints_json"],  # type: ignore[index]
        requested_by=row["requested_by"],  # type: ignore[index]
        operator_id=row["operator_id"],  # type: ignore[index]
        decision_reason=row["decision_reason"],  # type: ignore[index]
        edits_json=row["edits_json"],  # type: ignore[index]
        failure_reason=row["failure_reason"],  # type: ignore[index]
        created_at=parse_dt(row["created_at"]),  # type: ignore[index,arg-type]
        updated_at=parse_dt(row["updated_at"]),  # type: ignore[index,arg-type]
    )


class ActivityPlanRepository(RepositoryBase):
    """SQLite-backed access to the `activity_plans` table."""

    def create_draft(
        self,
        *,
        circle_id: str,
        template_id: str | None,
        activity_id: str | None,
        model_provider: str,
        model_name: str,
        prompt_version: str,
        prompt_text: str,
        request_payload_json: str,
        operator_constraints_json: str,
        requested_by: str | None,
    ) -> ActivityPlan:
        plan_id = new_id("plan")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO activity_plans (
                id, circle_id, template_id, activity_id, status,
                model_provider, model_name, prompt_version, prompt_text,
                request_payload_json, response_json, summary_text,
                requires_review_flags_json, operator_constraints_json,
                requested_by, operator_id, decision_reason, edits_json,
                failure_reason, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, 'draft',
                ?, ?, ?, ?,
                ?, NULL, NULL,
                '[]', ?,
                ?, NULL, NULL, NULL,
                NULL, ?, ?
            )
            """,
            (
                plan_id,
                circle_id,
                template_id,
                activity_id,
                model_provider,
                model_name,
                prompt_version,
                prompt_text,
                request_payload_json,
                operator_constraints_json,
                requested_by,
                now,
                now,
            ),
        )
        row = self.fetchone("SELECT * FROM activity_plans WHERE id = ?", (plan_id,))
        if row is None:
            raise RuntimeError(f"Failed to create activity plan draft {plan_id}")
        return _row_to_plan(row)

    def mark_generated(
        self,
        *,
        plan_id: str,
        response_json: str,
        summary_text: str,
        requires_review_flags_json: str,
    ) -> ActivityPlan:
        now = utc_now_iso()
        self.execute(
            """
            UPDATE activity_plans
            SET status = 'generated',
                response_json = ?,
                summary_text = ?,
                requires_review_flags_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (response_json, summary_text, requires_review_flags_json, now, plan_id),
        )
        return self.get_required(plan_id)

    def mark_failed(self, *, plan_id: str, failure_reason: str) -> ActivityPlan:
        now = utc_now_iso()
        self.execute(
            """
            UPDATE activity_plans
            SET status = 'failed',
                failure_reason = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (failure_reason, now, plan_id),
        )
        return self.get_required(plan_id)

    def record_decision(
        self,
        *,
        plan_id: str,
        decision: str,
        operator_id: str,
        reason: str | None,
        edits_json: str | None,
    ) -> ActivityPlan:
        if decision not in {"approved", "rejected", "edited"}:
            raise ValueError(f"Unsupported decision {decision!r}")
        now = utc_now_iso()
        self.execute(
            """
            UPDATE activity_plans
            SET status = ?,
                operator_id = ?,
                decision_reason = ?,
                edits_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (decision, operator_id, reason, edits_json, now, plan_id),
        )
        return self.get_required(plan_id)

    def get_plan(self, plan_id: str) -> ActivityPlan | None:
        row = self.fetchone("SELECT * FROM activity_plans WHERE id = ?", (plan_id,))
        if row is None:
            return None
        return _row_to_plan(row)

    def get_required(self, plan_id: str) -> ActivityPlan:
        plan = self.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Activity plan {plan_id} not found")
        return plan

    def list_for_circle(self, *, circle_id: str, limit: int = 20) -> list[ActivityPlan]:
        rows = self.fetchall(
            """
            SELECT * FROM activity_plans
            WHERE circle_id = ?
            ORDER BY created_at DESC, id
            LIMIT ?
            """,
            (circle_id, limit),
        )
        return [_row_to_plan(row) for row in rows]
