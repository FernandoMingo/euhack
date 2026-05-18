from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
