from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import connect  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.seed import seed_activity_templates  # noqa: E402


class OperatorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(db_path=Path(self._tmp.name) / "test.db")
        self.client = TestClient(self.app)

        # Build a small fixture: one verified professional → two residents
        # → one activity. FK constraints in the schema require these to be
        # real rows, so we set them up here rather than using placeholder IDs.
        signup = self.client.post(
            "/api/professionals/signup",
            json={
                "full_name": "Doc",
                "role": "huisarts",
                "email": "doc@operator.example.nl",
                "agb_code": "01024520",
                "big_number": "12345678",
            },
        ).json()
        self.professional_id = signup["professional"]["id"]

        def _refer(first_name: str, email: str) -> str:
            ref = self.client.post(
                "/api/referrals",
                json={
                    "professional_id": signup["professional"]["id"],
                    "profile": {
                        "first_name": first_name,
                        "email": email,
                        "preferred_language": "nl",
                        "city": "Amsterdam",
                        "social_comfort": "small_group_low_pressure",
                        "preferred_group_size_min": 3,
                        "preferred_group_size_max": 6,
                        "cost_sensitivity": "free_or_low_cost",
                    },
                },
            )
            return ref.json()["resident"]["id"]

        self.resident_a = _refer("Alice", "alice@operator.example.nl")
        self.resident_b = _refer("Bob", "bob@operator.example.nl")

        venue = self.client.post(
            "/api/venues",
            json={"name": "V", "address": "A", "city": "Amsterdam"},
        ).json()
        self.activity_id = self.client.post(
            "/api/activities",
            json={
                "title": "Walk",
                "activity_type": "walk",
                "venue_id": venue["id"],
                "start_at": "2026-06-01T10:00:00+02:00",
                "end_at": "2026-06-01T11:00:00+02:00",
                "capacity": 5,
                "risk_level": "low",
                "approval_status": "approved",
            },
        ).json()["id"]

    def test_matching_run_and_candidates(self) -> None:
        run = self.client.post(
            "/api/operator/matching-runs",
            json={
                "run_type": "activity_ranking",
                "model_version": "v0.1",
                "score_algorithm": "linear_weighted",
            },
        )
        self.assertEqual(run.status_code, 201, run.text)
        run_id = run.json()["id"]

        c1 = self.client.post(
            f"/api/operator/matching-runs/{run_id}/candidates",
            json={
                "total_score": 0.92,
                "rank_position": 1,
                "hard_constraints_passed": True,
                "activity_id": self.activity_id,
            },
        )
        self.assertEqual(c1.status_code, 201, c1.text)
        c2 = self.client.post(
            f"/api/operator/matching-runs/{run_id}/candidates",
            json={
                "total_score": 0.85,
                "rank_position": 2,
                "hard_constraints_passed": True,
                "resident_id": self.resident_a,
            },
        )
        self.assertEqual(c2.status_code, 201, c2.text)

        top = self.client.get(
            f"/api/operator/matching-runs/{run_id}/candidates?limit=5"
        )
        self.assertEqual(top.status_code, 200)
        self.assertEqual(len(top.json()), 2)
        self.assertEqual(top.json()[0]["rank_position"], 1)

    def test_peer_rating_flow(self) -> None:
        rating = self.client.post(
            "/api/operator/peer-ratings",
            json={
                "activity_id": self.activity_id,
                "rater_resident_id": self.resident_a,
                "ratee_resident_id": self.resident_b,
                "comfort_to_be_with": 4,
                "respectful_behavior": 5,
                "reliability_showed_up": 5,
                "group_contribution": 4,
            },
        )
        self.assertEqual(rating.status_code, 201, rating.text)
        rating_id = rating.json()["id"]

        listed = self.client.get(
            f"/api/operator/peer-ratings/resident/{self.resident_b}"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        rollup = self.client.post(
            "/api/operator/peer-rollups",
            json={
                "resident_id": self.resident_b,
                "model_version": "v0.1",
                "comfort_to_be_with_score": 4.0,
                "rating_count": 1,
            },
        )
        self.assertEqual(rollup.status_code, 201, rollup.text)

        flag = self.client.post(
            f"/api/operator/peer-ratings/{rating_id}/flag",
            json={"flag_type": "outlier", "severity": "low", "details": "edge case"},
        )
        self.assertEqual(flag.status_code, 201, flag.text)

    def test_peer_rating_rejects_self_rating(self) -> None:
        r = self.client.post(
            "/api/operator/peer-ratings",
            json={
                "activity_id": self.activity_id,
                "rater_resident_id": self.resident_a,
                "ratee_resident_id": self.resident_a,
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_referral_matching_workflow_exposes_review_views(self) -> None:
        with connect(db_path=self.app.state.db_path) as conn:
            seed_activity_templates(conn=conn)
            conn.commit()

        referral_ids = []
        for idx, first_name in enumerate(("Sofia", "Marco", "Aisha")):
            response = self.client.post(
                "/api/referrals",
                json={
                    "professional_id": self.professional_id,
                    "profile": {
                        "first_name": first_name,
                        "email": f"{first_name.lower()}@workflow.example.nl",
                        "preferred_language": "nl",
                        "city": "Amsterdam",
                        "social_comfort": "small_group_low_pressure",
                        "preferred_group_size_min": 2,
                        "preferred_group_size_max": 4,
                        "cost_sensitivity": "free_or_low_cost",
                        "interests": ["photography", "outdoor"],
                        "activities": ["photography_walk"],
                        "availability": [
                            {
                                "weekday": "sat",
                                "start_time_local": "09:00",
                                "end_time_local": "12:00",
                            }
                        ],
                    },
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            referral_ids.append(response.json()["referral"]["id"])

        workflow = self.client.post(
            f"/api/operator/referrals/{referral_ids[0]}/matching-workflow",
            json={
                "top_n_activities": 3,
                "top_n_groups": 2,
                "min_group_size": 2,
                "max_group_size": 4,
            },
        )
        self.assertEqual(workflow.status_code, 201, workflow.text)
        body = workflow.json()
        self.assertNotEqual(body["activity_ranking_run_id"], "")
        self.assertGreaterEqual(len(body["top_activity_results"]), 1)
        self.assertIsNotNone(body["circle_matching_run_id"])

        review = self.client.get(
            f"/api/operator/matching-runs/{body['circle_matching_run_id']}/review"
        )
        self.assertEqual(review.status_code, 200, review.text)
        candidates = review.json()["candidates"]
        self.assertGreaterEqual(len(candidates), 1)
        self.assertTrue(any(c["explanation"] for c in candidates))

        proposed = self.client.get("/api/operator/proposed-circles")
        self.assertEqual(proposed.status_code, 200, proposed.text)
        self.assertGreaterEqual(len(proposed.json()["circles"]), 1)

    def test_operator_decision_and_invitation_promotion_are_audited(self) -> None:
        decision = self.client.post(
            f"/api/operator/activities/{self.activity_id}/decisions",
            json={
                "operator_id": "operator_1",
                "decision": "approved",
                "reason": "Looks suitable",
            },
        )
        self.assertEqual(decision.status_code, 201, decision.text)

        circle = self.client.post(
            f"/api/activities/{self.activity_id}/circles",
            json={"status": "proposed", "fit_score": 0.8, "shared_signals_json": "{}"},
        )
        self.assertEqual(circle.status_code, 201, circle.text)
        circle_id = circle.json()["id"]
        for resident_id in (self.resident_a, self.resident_b):
            member = self.client.post(
                f"/api/circles/{circle_id}/members",
                json={"resident_id": resident_id},
            )
            self.assertEqual(member.status_code, 201, member.text)

        promotion = self.client.post(
            f"/api/operator/circles/{circle_id}/send-invitations?actor_id=operator_1"
        )
        self.assertEqual(promotion.status_code, 201, promotion.text)
        self.assertEqual(len(promotion.json()["invitations"]), 2)

        audit = self.client.get(f"/api/operator/audit-events?entity_id={circle_id}")
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertTrue(
            any(event["action"] == "circle.invitations_sent" for event in audit.json())
        )


if __name__ == "__main__":
    unittest.main()
