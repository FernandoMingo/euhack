from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402


def _signup_and_refer(client: TestClient) -> dict:
    signup = client.post(
        "/api/professionals/signup",
        json={
            "full_name": "Dr. Test",
            "role": "huisarts",
            "email": "doc@residents-test.nl",
            "agb_code": "01024501",
            "big_number": "11111111",
        },
    ).json()
    referral = client.post(
        "/api/referrals",
        json={
            "professional_id": signup["professional"]["id"],
            "profile": {
                "first_name": "Sofia",
                "email": "sofia.r@example.com",
                "preferred_language": "nl",
                "city": "Amsterdam",
                "social_comfort": "small_group_low_pressure",
                "preferred_group_size_min": 3,
                "preferred_group_size_max": 6,
                "cost_sensitivity": "free_or_low_cost",
            },
        },
    ).json()
    return referral


class ResidentsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(db_path=Path(self._tmp.name) / "test.db")
        self.client = TestClient(self.app)
        self.referral = _signup_and_refer(self.client)
        self.resident_id = self.referral["resident"]["id"]

    def test_get_resident(self) -> None:
        r = self.client.get(f"/api/residents/{self.resident_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["first_name"], "Sofia")

    def test_list_residents_filters_by_status(self) -> None:
        r = self.client.get("/api/residents?status=active")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        r2 = self.client.get("/api/residents?status=withdrawn")
        self.assertEqual(r2.json(), [])

    def test_update_status_to_paused(self) -> None:
        r = self.client.patch(
            f"/api/residents/{self.resident_id}/status",
            json={"status": "paused"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "paused")

    def test_add_preference_and_availability_and_avoidance(self) -> None:
        pref = self.client.post(
            f"/api/residents/{self.resident_id}/preferences",
            json={"preference_type": "interest", "value": "photography"},
        )
        self.assertEqual(pref.status_code, 201)
        self.assertEqual(pref.json()["value"], "photography")

        avail = self.client.post(
            f"/api/residents/{self.resident_id}/availability",
            json={"weekday": "sat", "start_time_local": "10:00", "end_time_local": "12:00"},
        )
        self.assertEqual(avail.status_code, 201)

        avoid = self.client.post(
            f"/api/residents/{self.resident_id}/avoidances",
            json={"value": "alcohol"},
        )
        self.assertEqual(avoid.status_code, 201)

    def test_list_resident_consents(self) -> None:
        r = self.client.get(f"/api/residents/{self.resident_id}/consents")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["status"], "active")

    def test_unknown_resident_returns_404(self) -> None:
        r = self.client.get("/api/residents/does-not-exist")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
