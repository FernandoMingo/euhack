from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    ActivityPlanRepository,
    ActivityRepository,
    ActivityTemplateRepository,
    ResidentRepository,
    connect,
    init_db,
)
from app.seed import seed_activity_templates  # noqa: E402
from app.services import (  # noqa: E402
    ActivityPlanningService,
    LLMConfigurationError,
    LLMResponse,
    LLMResponseError,
    OpenAIChatLLMClient,
    OUTPUT_LANGUAGE,
    PROMPT_VERSION,
)


class _FakeLLMClient:
    """Test double recording prompts and returning canned JSON responses."""

    model_provider = "fake"

    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
        model_name: str = "fake-model-v1",
    ) -> None:
        self._response = response
        self._error = error
        self._model_name = model_name
        self.calls: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_json(
        self,
        *,
        prompt: str,
        json_schema: Mapping[str, Any],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "json_schema": dict(json_schema),
            }
        )
        if self._error is not None:
            raise self._error
        content = self._response or {}
        return LLMResponse(
            content=content,
            raw_text=json.dumps(content, sort_keys=True),
            model_provider=self.model_provider,
            model_name=self._model_name,
        )


def _good_response() -> dict[str, Any]:
    return {
        "language": "English",
        "title": "Saturday Photography Walk",
        "description": (
            "A gentle 90-minute photography walk along the canals with a "
            "focused, beginner-friendly pace."
        ),
        "duration_minutes": 90,
        "venue_research": {
            "search_area": "Rotterdam",
            "selected_venue_name": "Het Park",
            "selected_venue_address": "Parkkade, 3016 Rotterdam",
            "venue_url": "https://rotterdam.info/locaties/het-park/",
            "why_feasible": "Central outdoor route with accessible paths.",
            "sources_checked": [
                {
                    "title": "Het Park",
                    "url": "https://rotterdam.info/locaties/het-park/",
                    "finding": "Large public park suitable for a short walk.",
                }
            ],
        },
        "schedule_suggestions": [
            {
                "weekday": "sat",
                "time_window": "10:00-11:30",
                "rationale": "Aligns with shared morning availability.",
            }
        ],
        "venue_requirements": [
            "Outdoor meeting point near accessible transit.",
        ],
        "accessibility_considerations": [
            "Step-free route, clear meeting point.",
        ],
        "safety_notes": [
            "Operator-approved facilitator present.",
        ],
        "materials": ["Phone or camera, water bottle"],
        "invitation_copy": {
            "subject": "A relaxed photo walk this Saturday",
            "body": "Join a small group for a short photo walk this Saturday.",
        },
        "rationale": {
            "summary": (
                "The plan matches the group's shared interest in photography "
                "and Saturday morning availability."
            ),
            "linked_signals": [
                {
                    "signal": "shared_availability:sat_morning",
                    "explanation": "Every member is available Saturday morning.",
                }
            ],
        },
        "requires_review_flags": [
            "operator_to_confirm_specific_venue",
        ],
    }


def _seed_fixture(db_path: Path) -> tuple[str, str, str]:
    """Create a minimal proposed circle and return (circle_id, template_id, member_ids)."""
    init_db(db_path=db_path)
    with connect(db_path=db_path) as conn:
        seed_activity_templates(conn=conn)
        activities = ActivityRepository(conn)
        residents = ResidentRepository(conn)
        templates = ActivityTemplateRepository(conn)
        template = templates.get_template_by_code("photography_walk")
        assert template is not None
        member_ids: list[str] = []
        for idx in range(3):
            resident = residents.create_resident(
                first_name=f"Resident {idx}",
                email=f"resident{idx}@example.com",
                preferred_language="English",
                city="Amsterdam",
                social_comfort="small_group_low_pressure",
                preferred_group_size_min=3,
                preferred_group_size_max=6,
                cost_sensitivity="free_or_low_cost",
            )
            member_ids.append(resident.id)
        circle = activities.create_circle(
            template_id=template.id,
            status="proposed",
            fit_score=0.74,
            shared_signals_json=json.dumps(
                {
                    "shared_availability": ["sat_morning"],
                    "shared_interests": ["interest:photography"],
                },
                sort_keys=True,
            ),
        )
        for member_id in member_ids:
            activities.add_circle_member(circle_id=circle.id, resident_id=member_id)
        conn.commit()
        return circle.id, template.id, member_ids[0]


class ActivityPlanningServiceTests(unittest.TestCase):
    def test_fake_client_produces_persisted_plan_with_audit_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, template_id, _member_id = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                fake_client = _FakeLLMClient(response=_good_response())
                service = ActivityPlanningService(conn, llm_client=fake_client)
                result = service.generate_plan_for_circle(
                    circle_id=circle_id,
                    operator_constraints={"max_attendees": 6, "output_language": "Dutch"},
                    requested_by="operator_1",
                )

                self.assertEqual(result.plan.status, "generated")
                self.assertEqual(result.plan.template_id, template_id)
                self.assertEqual(result.plan.model_provider, "fake")
                self.assertEqual(result.plan.model_name, "fake-model-v1")
                self.assertEqual(result.plan.prompt_version, PROMPT_VERSION)
                self.assertIsNotNone(result.plan.summary_text)
                self.assertIn("operator_to_confirm_specific_venue", result.requires_review_flags)
                self.assertEqual(len(fake_client.calls), 1)

                stored = ActivityPlanRepository(conn).get_required(result.plan.id)
                self.assertEqual(stored.status, "generated")
                self.assertIsNotNone(stored.response_json)
                self.assertEqual(
                    json.loads(stored.operator_constraints_json),
                    {"max_attendees": 6, "output_language": "Dutch"},
                )
                self.assertEqual(result.request_payload["output_language"], OUTPUT_LANGUAGE)
                self.assertEqual(result.response_content["language"], OUTPUT_LANGUAGE)

                audit = conn.execute(
                    "SELECT action FROM audit_events WHERE entity_id = ? ORDER BY created_at",
                    (result.plan.id,),
                ).fetchall()
                actions = [row["action"] for row in audit]
                self.assertIn("activity_plan.requested", actions)
                self.assertIn("activity_plan.generated", actions)

    def test_prompt_payload_excludes_clinical_and_peer_rating_data(self) -> None:
        """The prompt sent to the LLM must never contain forbidden fields."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, _template_id, _ = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                fake_client = _FakeLLMClient(response=_good_response())
                service = ActivityPlanningService(conn, llm_client=fake_client)
                result = service.generate_plan_for_circle(
                    circle_id=circle_id,
                    operator_constraints={},
                    requested_by=None,
                )

            payload = result.request_payload
            self.assertNotIn("medical", json.dumps(payload).lower())
            self.assertNotIn("diagnos", json.dumps(payload).lower())
            self.assertNotIn("peer_rating", json.dumps(payload).lower())
            self.assertNotIn("therapy", json.dumps(payload).lower())
            self.assertEqual(payload["circle"]["member_count"], 3)
            self.assertNotIn("members", payload["circle"])
            self.assertEqual(payload["venue_search"]["city"], "Rotterdam")
            self.assertEqual(payload["output_language"], "English")
            self.assertEqual(fake_client.calls[0]["json_schema"]["properties"]["language"]["enum"], ["English"])

            self.assertEqual(len(fake_client.calls), 1)
            sent_prompt = fake_client.calls[0]["prompt"].lower()
            for forbidden in ("diagnos", "therapy", "medication", "peer_rating"):
                self.assertNotIn(forbidden, sent_prompt)
            self.assertIn("rotterdam", sent_prompt)
            self.assertIn("venue options online", sent_prompt)
            self.assertIn("write all returned", sent_prompt)

    def test_missing_llm_client_raises_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, _, _ = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                service = ActivityPlanningService(conn, llm_client=None)
                with self.assertRaises(LLMConfigurationError):
                    service.generate_plan_for_circle(
                        circle_id=circle_id,
                        operator_constraints={},
                        requested_by="operator_1",
                    )

    def test_missing_openai_api_key_raises_when_used(self) -> None:
        """The real OpenAI client must fail explicitly without an API key."""
        client = OpenAIChatLLMClient(api_key=None)
        with self.assertRaises(LLMConfigurationError):
            client.generate_json(
                prompt="hi",
                json_schema={"type": "object"},
                system_prompt=None,
            )

    def test_generation_does_not_create_invitations_or_activities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, _, _ = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                service = ActivityPlanningService(
                    conn, llm_client=_FakeLLMClient(response=_good_response())
                )
                service.generate_plan_for_circle(
                    circle_id=circle_id,
                    operator_constraints={},
                    requested_by="operator_1",
                )
                invitations = conn.execute("SELECT COUNT(*) FROM invitations").fetchone()[0]
                self.assertEqual(invitations, 0)
                activities = conn.execute(
                    "SELECT COUNT(*) FROM activities"
                ).fetchone()[0]
                self.assertEqual(activities, 0)
                circle_row = conn.execute(
                    "SELECT status FROM circles WHERE id = ?", (circle_id,)
                ).fetchone()
                self.assertEqual(circle_row["status"], "proposed")

    def test_llm_failure_is_persisted_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, _, _ = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                fake_client = _FakeLLMClient(error=LLMResponseError("boom"))
                service = ActivityPlanningService(conn, llm_client=fake_client)
                with self.assertRaises(LLMResponseError):
                    service.generate_plan_for_circle(
                        circle_id=circle_id,
                        operator_constraints={},
                        requested_by="operator_1",
                    )
                row = conn.execute(
                    "SELECT status, failure_reason FROM activity_plans"
                ).fetchone()
                self.assertEqual(row["status"], "failed")
                self.assertIn("boom", row["failure_reason"])
                audit_actions = [
                    r["action"]
                    for r in conn.execute(
                        "SELECT action FROM audit_events WHERE entity_type = 'activity_plan'"
                    ).fetchall()
                ]
                self.assertIn("activity_plan.requested", audit_actions)
                self.assertIn("activity_plan.failed", audit_actions)

    def test_non_english_response_is_rejected_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, _, _ = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                response = _good_response()
                response["language"] = "Dutch"
                service = ActivityPlanningService(
                    conn, llm_client=_FakeLLMClient(response=response)
                )
                with self.assertRaises(LLMResponseError):
                    service.generate_plan_for_circle(
                        circle_id=circle_id,
                        operator_constraints={},
                        requested_by="operator_1",
                    )
                row = conn.execute(
                    "SELECT status, failure_reason FROM activity_plans"
                ).fetchone()
                self.assertEqual(row["status"], "failed")
                self.assertIn("language must be 'English'", row["failure_reason"])

    def test_operator_decision_is_recorded_with_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "plan.db"
            circle_id, _, _ = _seed_fixture(db_path)
            with connect(db_path=db_path) as conn:
                service = ActivityPlanningService(
                    conn, llm_client=_FakeLLMClient(response=_good_response())
                )
                result = service.generate_plan_for_circle(
                    circle_id=circle_id,
                    operator_constraints={},
                    requested_by="operator_1",
                )
                updated = service.record_operator_decision(
                    plan_id=result.plan.id,
                    operator_id="operator_1",
                    decision="approved",
                    reason="Looks great",
                    edits={"title": "Saturday Photo Walk"},
                )
                self.assertEqual(updated.status, "approved")
                self.assertEqual(updated.operator_id, "operator_1")
                self.assertIsNotNone(updated.edits_json)
                actions = [
                    r["action"]
                    for r in conn.execute(
                        "SELECT action FROM audit_events WHERE entity_id = ?",
                        (result.plan.id,),
                    ).fetchall()
                ]
                self.assertIn("activity_plan.decision.approved", actions)


if __name__ == "__main__":
    unittest.main()
