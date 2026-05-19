"""Auditable LLM-backed activity planning workflow.

The service turns a *proposed* circle (template-anchored or anchored to a
draft activity) into an operator-reviewable activity plan. The LLM only
**proposes**; the operator must approve before invitations are sent.

Hard guardrails enforced in this module:

- No clinical/medical data is read or sent to the LLM. Only safe product
  fields (template attributes/tags, shared availability buckets, shared
  interest keys, and aggregate member-level non-sensitive summaries) are
  ever included in the prompt payload.
- Peer ratings are never read.
- The service never creates an `activities` row, never approves an
    activity, and never sends invitations. Approval/edit/reject of the
  plan is recorded; downstream actions remain manual.
- Every request, response, and decision is persisted (full prompt +
  structured JSON response + audit events).
- The prompt template, model name, and structured JSON schema are
  version-pinned constants so the artifact is reproducible.
- Venue research is constrained to Rotterdam and no user data is sent to
  the LLM.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from sqlite3 import Connection
from typing import Any

from app.dataclasses import ActivityPlan
from app.repositories import (
    ActivityPlanRepository,
    ActivityRepository,
    ActivityTemplateRepository,
)
from app.repositories.base import new_id, utc_now_iso
from app.services.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMResponseError,
)


logger = logging.getLogger(__name__)


OUTPUT_LANGUAGE = "English"
PROMPT_VERSION = "activity_plan.rotterdam_web_v3"

PROMPT_SYSTEM = (
    "You are a Rotterdam activity planner for city operators. Research real "
    "venues and current practical details in Rotterdam before proposing the "
    "plan. Use the activity template, shared group signals, and operator "
    "constraints to select a feasible venue and schedule. Prefer accessible, "
    "low-pressure, easy-to-reach options. Write every user-facing string in "
    "English. Return only valid JSON matching the requested schema."
)

PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "language",
        "title",
        "description",
        "duration_minutes",
        "venue_research",
        "schedule_suggestions",
        "venue_requirements",
        "accessibility_considerations",
        "safety_notes",
        "materials",
        "invitation_copy",
        "rationale",
        "requires_review_flags",
    ],
    "properties": {
        "language": {"type": "string", "enum": [OUTPUT_LANGUAGE]},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "duration_minutes": {"type": "integer", "minimum": 15, "maximum": 480},
        "venue_research": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "search_area",
                "selected_venue_name",
                "selected_venue_address",
                "venue_url",
                "why_feasible",
                "sources_checked",
            ],
            "properties": {
                "search_area": {"type": "string"},
                "selected_venue_name": {"type": "string"},
                "selected_venue_address": {"type": "string"},
                "venue_url": {"type": "string"},
                "why_feasible": {"type": "string"},
                "sources_checked": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title", "url", "finding"],
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "finding": {"type": "string"},
                        },
                    },
                    "minItems": 1,
                    "maxItems": 8,
                },
            },
        },
        "schedule_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["weekday", "time_window", "rationale"],
                "properties": {
                    "weekday": {"type": "string"},
                    "time_window": {"type": "string"},
                    "rationale": {"type": "string"},
                },
            },
            "minItems": 1,
            "maxItems": 5,
        },
        "venue_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 10,
        },
        "accessibility_considerations": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
        "safety_notes": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
        "materials": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 20,
        },
        "invitation_copy": {
            "type": "object",
            "additionalProperties": False,
            "required": ["subject", "body"],
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
        },
        "rationale": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "linked_signals"],
            "properties": {
                "summary": {"type": "string"},
                "linked_signals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["signal", "explanation"],
                        "properties": {
                            "signal": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                    },
                    "minItems": 1,
                    "maxItems": 15,
                },
            },
        },
        "requires_review_flags": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
    },
}


# Substrings whose presence anywhere in the prompt payload is treated as a
# privacy violation. We use simple, lowercased substring matching rather than
# a heavyweight classifier because the only input we control is a small set
# of structured fields and we want a hard, audit-friendly guarantee.
_FORBIDDEN_KEY_SUBSTRINGS: tuple[str, ...] = (
    "diagnos",
    "medication",
    "therapy",
    "clinical",
    "peer_rating",
    "peer_ratings",
    "rating_score",
    "comfort_to_be_with",
    "respectful_behavior",
    "reliability_showed_up",
    "group_contribution",
    "ssn",
    "medical_record",
)


class PromptSafetyError(RuntimeError):
    """Raised when the assembled prompt payload contains forbidden content."""


@dataclass(slots=True, frozen=True)
class PlanGenerationResult:
    """Public return value of :meth:`ActivityPlanningService.generate_plan_for_circle`."""

    plan: ActivityPlan
    request_payload: dict[str, Any]
    response_content: dict[str, Any] | None
    summary_text: str | None
    requires_review_flags: tuple[str, ...]


class ActivityPlanningService:
    """Compose the LLM, repositories, and audit events into a single workflow.

    The service is intentionally thin: it builds a deterministic prompt
    payload, persists the prompt before calling the LLM, persists the
    parsed response (or failure reason) after, and writes a small set of
    audit events. Routes should call this service directly.
    """

    def __init__(
        self,
        conn: Connection,
        *,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.conn = conn
        self.plans = ActivityPlanRepository(conn)
        self.activities = ActivityRepository(conn)
        self.templates = ActivityTemplateRepository(conn)
        self._llm_client = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_plan_for_circle(
        self,
        *,
        circle_id: str,
        operator_constraints: dict[str, Any] | None = None,
        requested_by: str | None = None,
    ) -> PlanGenerationResult:
        """Generate (and persist) an activity plan draft for ``circle_id``."""
        client = self._require_llm_client()

        circle = self.activities.get_circle(circle_id)
        if circle is None:
            raise ValueError(f"Circle {circle_id} not found")

        template = None
        if circle.template_id is not None:
            for candidate in self.templates.list_templates():
                if candidate.id == circle.template_id:
                    template = candidate
                    break
        activity = None
        if circle.activity_id is not None:
            activity = self.activities.get_activity(circle.activity_id)
            if template is None and activity is not None:
                template = self.templates.get_template_by_code(activity.activity_type)

        if template is None:
            raise ValueError(
                f"Circle {circle_id} has no template or resolvable activity_type "
                "to anchor the activity plan"
            )

        members = self.activities.list_circle_members(circle_id=circle_id)
        if not members:
            raise ValueError(f"Circle {circle_id} has no members to plan for")

        operator_constraints = dict(operator_constraints or {})
        tags = self.templates.get_tags(template.id)
        request_payload = self._build_request_payload(
            circle=circle,
            template=template,
            template_tags=tags,
            activity=activity,
            member_count=len(members),
            operator_constraints=operator_constraints,
        )
        _ensure_no_forbidden_content(request_payload)
        prompt_text = self._render_prompt(request_payload)

        plan = self.plans.create_draft(
            circle_id=circle_id,
            template_id=template.id,
            activity_id=circle.activity_id,
            model_provider=client.model_provider,
            model_name=client.model_name,
            prompt_version=PROMPT_VERSION,
            prompt_text=prompt_text,
            request_payload_json=json.dumps(request_payload, sort_keys=True),
            operator_constraints_json=json.dumps(operator_constraints, sort_keys=True),
            requested_by=requested_by,
        )
        self._add_audit_event(
            actor_type="system" if requested_by is None else "operator",
            actor_id=requested_by,
            action="activity_plan.requested",
            entity_type="activity_plan",
            entity_id=plan.id,
            metadata={
                "circle_id": circle_id,
                "template_id": template.id,
                "model_provider": client.model_provider,
                "model_name": client.model_name,
                "prompt_version": PROMPT_VERSION,
            },
        )
        self.conn.commit()

        try:
            llm_response = client.generate_json(
                prompt=prompt_text,
                json_schema=PLAN_JSON_SCHEMA,
                system_prompt=PROMPT_SYSTEM,
            )
            _ensure_english_response(llm_response.content)
        except (LLMConfigurationError, LLMResponseError) as exc:
            plan = self.plans.mark_failed(plan_id=plan.id, failure_reason=str(exc))
            self._add_audit_event(
                actor_type="system",
                actor_id=requested_by,
                action="activity_plan.failed",
                entity_type="activity_plan",
                entity_id=plan.id,
                metadata={"error": str(exc)},
            )
            self.conn.commit()
            raise

        flags = _extract_review_flags(llm_response.content)
        summary_text = _build_summary_text(template_title=template.title, response=llm_response.content)

        plan = self.plans.mark_generated(
            plan_id=plan.id,
            response_json=json.dumps(llm_response.content, sort_keys=True),
            summary_text=summary_text,
            requires_review_flags_json=json.dumps(list(flags), sort_keys=True),
        )
        self._add_audit_event(
            actor_type="system",
            actor_id=requested_by,
            action="activity_plan.generated",
            entity_type="activity_plan",
            entity_id=plan.id,
            metadata={
                "model_provider": llm_response.model_provider,
                "model_name": llm_response.model_name,
                "prompt_version": PROMPT_VERSION,
                "review_flag_count": len(flags),
            },
        )
        self.conn.commit()

        return PlanGenerationResult(
            plan=plan,
            request_payload=request_payload,
            response_content=llm_response.content,
            summary_text=summary_text,
            requires_review_flags=tuple(flags),
        )

    def get_plan(self, plan_id: str) -> ActivityPlan | None:
        return self.plans.get_plan(plan_id)

    def list_plans_for_circle(self, *, circle_id: str, limit: int = 20) -> list[ActivityPlan]:
        return self.plans.list_for_circle(circle_id=circle_id, limit=limit)

    def record_operator_decision(
        self,
        *,
        plan_id: str,
        operator_id: str,
        decision: str,
        reason: str | None = None,
        edits: dict[str, Any] | None = None,
    ) -> ActivityPlan:
        if decision not in {"approved", "rejected", "edited"}:
            raise ValueError(f"Unsupported decision {decision!r}")
        if self.plans.get_plan(plan_id) is None:
            raise ValueError(f"Activity plan {plan_id} not found")
        edits_json = json.dumps(edits, sort_keys=True) if edits is not None else None
        plan = self.plans.record_decision(
            plan_id=plan_id,
            decision=decision,
            operator_id=operator_id,
            reason=reason,
            edits_json=edits_json,
        )
        self._add_audit_event(
            actor_type="operator",
            actor_id=operator_id,
            action=f"activity_plan.decision.{decision}",
            entity_type="activity_plan",
            entity_id=plan.id,
            metadata={
                "reason": reason,
                "has_edits": edits is not None,
            },
        )
        self.conn.commit()
        return plan

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_llm_client(self) -> LLMClient:
        if self._llm_client is None:
            raise LLMConfigurationError(
                "ActivityPlanningService was constructed without an LLM client. "
                "Provide one explicitly (e.g. OpenAIChatLLMClient) so plan "
                "generation has a clear, auditable model identity."
            )
        return self._llm_client

    def _build_request_payload(
        self,
        *,
        circle: Any,
        template: Any,
        template_tags: list[str],
        activity: Any,
        member_count: int,
        operator_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        shared_signals = _safe_parse_shared_signals(circle.shared_signals_json)
        payload: dict[str, Any] = {
            "prompt_version": PROMPT_VERSION,
            "output_language": OUTPUT_LANGUAGE,
            "circle": {
                "id": circle.id,
                "status": circle.status,
                "fit_score": circle.fit_score,
                "member_count": member_count,
                "shared_availability": list(
                    shared_signals.get("shared_availability", []) or []
                ),
                "shared_interests": list(
                    shared_signals.get("shared_interests", []) or []
                ),
            },
            "venue_search": {
                "city": "Rotterdam",
                "country": "NL",
                "search_area": str(
                    operator_constraints.get("search_area")
                    or operator_constraints.get("neighborhood")
                    or "Rotterdam"
                ),
                "instruction": (
                    "Research actual venues in Rotterdam using this city and "
                    "the optional search_area."
                ),
            },
            "template": {
                "code": template.code,
                "title": template.title,
                "description": template.description,
                "family": template.family,
                "typical_duration_minutes": template.typical_duration_minutes,
                "typical_group_size_min": template.typical_group_size_min,
                "typical_group_size_max": template.typical_group_size_max,
                "typical_cost_band": template.typical_cost_band,
                "social_energy": template.social_energy,
                "setting": template.setting,
                "intensity": template.intensity,
                "noise_level": template.noise_level,
                "structure": template.structure,
                "risk_level": template.risk_level,
                "tags": list(template_tags),
            },
            "activity": None,
            "operator_constraints": operator_constraints,
        }
        if activity is not None:
            payload["activity"] = {
                "id": activity.id,
                "title": activity.title,
                "venue_id": activity.venue_id,
                "host_id": activity.host_id,
                "start_at": activity.start_at.isoformat(),
                "end_at": activity.end_at.isoformat(),
                "capacity": activity.capacity,
                "cost_cents": activity.cost_cents,
                "risk_level": activity.risk_level,
                "approval_status": activity.approval_status,
            }
        return payload

    def _render_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "Research real Rotterdam venue options online, then draft an "
            "operator-reviewable activity plan. Use the PAYLOAD as the source "
            "for activity fit and planning constraints. The plan must include "
            "the selected venue, address, source URLs checked, schedule, "
            "materials, invitation copy, and rationale. Write all returned "
            "text in English.\n\n"
            "PAYLOAD:\n"
            f"{json.dumps(payload, sort_keys=True, indent=2)}\n\n"
            "Return ONLY valid JSON matching the provided schema. Restrict "
            "venue research and recommendations to Rotterdam, Netherlands. "
            "Set `language` to \"English\"."
        )

    def _add_audit_event(
        self,
        *,
        actor_type: str,
        action: str,
        entity_type: str,
        metadata: dict[str, Any],
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


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _safe_parse_shared_signals(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _extract_review_flags(response: dict[str, Any]) -> list[str]:
    flags = response.get("requires_review_flags", []) or []
    if not isinstance(flags, list):
        return []
    return [str(flag) for flag in flags if isinstance(flag, (str, int, float))]


def _build_summary_text(*, template_title: str, response: dict[str, Any]) -> str:
    title = str(response.get("title") or template_title)
    duration = response.get("duration_minutes")
    duration_part = f" ({duration} min)" if isinstance(duration, (int, float)) else ""
    return f"Proposed plan: {title}{duration_part}. Awaiting operator review."


def _ensure_english_response(response: dict[str, Any]) -> None:
    if response.get("language") != OUTPUT_LANGUAGE:
        raise LLMResponseError(
            f"LLM response language must be {OUTPUT_LANGUAGE!r}; "
            f"got {response.get('language')!r}"
        )


def _ensure_no_forbidden_content(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True).lower()
    for substring in _FORBIDDEN_KEY_SUBSTRINGS:
        if substring in serialized:
            raise PromptSafetyError(
                f"Refusing to send prompt: payload contains forbidden token "
                f"{substring!r}. Only safe template + group signals may be sent."
            )


__all__ = [
    "ActivityPlanningService",
    "OUTPUT_LANGUAGE",
    "PLAN_JSON_SCHEMA",
    "PROMPT_SYSTEM",
    "PROMPT_VERSION",
    "PlanGenerationResult",
    "PromptSafetyError",
]
