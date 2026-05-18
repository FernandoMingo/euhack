from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402
from app.db import connect  # noqa: E402
from app.repositories import ActivityRepository, ResidentRepository  # noqa: E402
from app.seed import seed_activity_templates  # noqa: E402
from app.services.llm_client import LLMResponse  # noqa: E402


class _FakeLLMClient:
    model_provider = "fake"
    model_name = "fake-model-v1"

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.calls: list[str] = []

    def generate_json(
        self,
        *,
        prompt: str,
        json_schema: Mapping[str, Any],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        self.calls.append(prompt)
        return LLMResponse(
            content=self._response,
            raw_text=json.dumps(self._response, sort_keys=True),
            model_provider=self.model_provider,
            model_name=self.model_name,
        )


def _canned_plan() -> dict[str, Any]:
    return {
        "language": "English",
        "title": "Saturday Photography Walk",
        "description": "A relaxed photo walk along the canals.",
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
                "rationale": "Matches shared morning availability.",
            }
        ],
        "venue_requirements": ["Accessible outdoor meeting point"],
        "accessibility_considerations": ["Step-free route"],
        "safety_notes": ["Operator-approved facilitator"],
        "materials": ["Phone or camera"],
        "invitation_copy": {
            "subject": "A relaxed photo walk this Saturday",
            "body": "Join a small group for a short photo walk.",
        },
        "rationale": {
            "summary": "Matches group's photography interest and availability.",
            "linked_signals": [
                {
                    "signal": "shared_availability:sat_morning",
                    "explanation": "All members are free Saturday morning.",
                }
            ],
        },
        "requires_review_flags": ["operator_to_confirm_venue"],
    }


class ActivityPlanApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "api_plan.db"
        self.fake_client = _FakeLLMClient(_canned_plan())
        self.app = create_app(db_path=self.db_path, llm_client=self.fake_client)
        self.client = TestClient(self.app)

        with connect(db_path=self.db_path) as conn:
            seed_activity_templates(conn=conn)
            activities = ActivityRepository(conn)
            residents = ResidentRepository(conn)
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
                if idx == 0:
                    self.first_resident_id = resident.id
                self._add_member_later = resident.id

            template_row = conn.execute(
                "SELECT id FROM activity_templates WHERE code = 'photography_walk'"
            ).fetchone()
            assert template_row is not None
            self.template_id = template_row["id"]
            circle = activities.create_circle(
                template_id=self.template_id,
                status="proposed",
                fit_score=0.7,
                shared_signals_json=json.dumps(
                    {
                        "shared_availability": ["sat_morning"],
                        "shared_interests": ["interest:photography"],
                    },
                    sort_keys=True,
                ),
            )
            self.circle_id = circle.id
            for resident in residents.list_residents():
                activities.add_circle_member(circle_id=circle.id, resident_id=resident.id)
            conn.commit()

    def test_generate_plan_endpoint_returns_structured_plan(self) -> None:
        response = self.client.post(
            f"/api/operator/circles/{self.circle_id}/activity-plan",
            json={"operator_constraints": {"max_attendees": 6}, "requested_by": "operator_1"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["status"], "generated")
        self.assertEqual(body["model_provider"], "fake")
        self.assertEqual(body["plan"]["language"], "English")
        self.assertEqual(body["plan"]["title"], "Saturday Photography Walk")
        self.assertEqual(
            body["plan"]["venue_research"]["selected_venue_name"],
            "Het Park",
        )
        self.assertIn("operator_to_confirm_venue", body["requires_review_flags"])
        self.assertEqual(len(self.fake_client.calls), 1)

        get_resp = self.client.get(f"/api/operator/activity-plans/{body['id']}")
        self.assertEqual(get_resp.status_code, 200, get_resp.text)
        self.assertEqual(get_resp.json()["id"], body["id"])

        list_resp = self.client.get(
            f"/api/operator/circles/{self.circle_id}/activity-plans"
        )
        self.assertEqual(list_resp.status_code, 200, list_resp.text)
        self.assertEqual(len(list_resp.json()), 1)

        audit = self.client.get(f"/api/operator/audit-events?entity_id={body['id']}")
        self.assertEqual(audit.status_code, 200, audit.text)
        actions = [event["action"] for event in audit.json()]
        self.assertIn("activity_plan.requested", actions)
        self.assertIn("activity_plan.generated", actions)

    def test_missing_llm_client_returns_503(self) -> None:
        bare_app = create_app(
            db_path=Path(self._tmp.name) / "no_llm.db",
            llm_client=None,
        )
        bare_client = TestClient(bare_app)
        response = bare_client.post(
            f"/api/operator/circles/{self.circle_id}/activity-plan",
            json={"operator_constraints": {}},
        )
        self.assertEqual(response.status_code, 503, response.text)

    def test_decision_endpoint_records_audit(self) -> None:
        gen = self.client.post(
            f"/api/operator/circles/{self.circle_id}/activity-plan",
            json={"operator_constraints": {}, "requested_by": "operator_1"},
        )
        plan_id = gen.json()["id"]
        decision = self.client.post(
            f"/api/operator/activity-plans/{plan_id}/decision",
            json={
                "operator_id": "operator_1",
                "decision": "approved",
                "reason": "Looks suitable",
                "edits": {"title": "Saturday Photo Walk"},
            },
        )
        self.assertEqual(decision.status_code, 201, decision.text)
        self.assertEqual(decision.json()["status"], "approved")
        self.assertEqual(decision.json()["edits"], {"title": "Saturday Photo Walk"})

        invitations = self.client.get(f"/api/operator/audit-events?entity_id={plan_id}")
        actions = [event["action"] for event in invitations.json()]
        self.assertIn("activity_plan.decision.approved", actions)


if __name__ == "__main__":
    unittest.main()
