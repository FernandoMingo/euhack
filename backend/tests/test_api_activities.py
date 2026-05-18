from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402


class ActivitiesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(db_path=Path(self._tmp.name) / "test.db")
        self.client = TestClient(self.app)

        self.venue = self.client.post(
            "/api/venues",
            json={"name": "Vondelpark Entrance", "address": "Vondelpark", "city": "Amsterdam"},
        ).json()
        self.host = self.client.post(
            "/api/hosts",
            json={"full_name": "Anna", "host_type": "city_staff"},
        ).json()
        self.activity = self.client.post(
            "/api/activities",
            json={
                "title": "Photography Walk",
                "activity_type": "photography_walk",
                "venue_id": self.venue["id"],
                "host_id": self.host["id"],
                "start_at": "2026-05-23T10:30:00+02:00",
                "end_at": "2026-05-23T12:00:00+02:00",
                "capacity": 6,
                "risk_level": "low",
                "approval_status": "approved",
            },
        ).json()
        self.assertIn("id", self.activity)

        # A resident to attend / give feedback
        signup = self.client.post(
            "/api/professionals/signup",
            json={
                "full_name": "Doc",
                "role": "huisarts",
                "email": "doc@activities.example.nl",
                "agb_code": "01024509",
                "big_number": "12345678",
            },
        ).json()
        self.resident = self.client.post(
            "/api/referrals",
            json={
                "professional_id": signup["professional"]["id"],
                "profile": {
                    "first_name": "Sofia",
                    "email": "sofia@activities.example.nl",
                    "preferred_language": "nl",
                    "city": "Amsterdam",
                    "social_comfort": "small_group_low_pressure",
                    "preferred_group_size_min": 3,
                    "preferred_group_size_max": 6,
                    "cost_sensitivity": "free_or_low_cost",
                },
            },
        ).json()["resident"]

    def test_get_activity(self) -> None:
        r = self.client.get(f"/api/activities/{self.activity['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["title"], "Photography Walk")

    def test_create_circle_and_member(self) -> None:
        circle = self.client.post(
            f"/api/activities/{self.activity['id']}/circles",
            json={"status": "proposed", "fit_score": 0.9, "shared_signals_json": "[]"},
        )
        self.assertEqual(circle.status_code, 201)
        circle_id = circle.json()["id"]

        member = self.client.post(
            f"/api/circles/{circle_id}/members",
            json={"resident_id": self.resident["id"]},
        )
        self.assertEqual(member.status_code, 201)

    def test_record_attendance_and_feedback(self) -> None:
        att = self.client.post(
            f"/api/activities/{self.activity['id']}/attendance",
            json={
                "resident_id": self.resident["id"],
                "attendance_status": "attended",
                "check_in_at": "2026-05-23T10:35:00+02:00",
            },
        )
        self.assertEqual(att.status_code, 201)
        self.assertEqual(att.json()["attendance_status"], "attended")

        fb = self.client.post(
            f"/api/activities/{self.activity['id']}/feedback",
            json={
                "resident_id": self.resident["id"],
                "felt_after": "better",
                "activity_fit": True,
                "group_comfort": True,
                "would_repeat": True,
            },
        )
        self.assertEqual(fb.status_code, 201)
        self.assertEqual(fb.json()["felt_after"], "better")
        self.assertTrue(fb.json()["would_repeat"])

    def test_unknown_activity_404(self) -> None:
        r = self.client.get("/api/activities/missing")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
