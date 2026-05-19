from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402


class OnboardingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        # ignore_cleanup_errors works around Windows holding the SQLite WAL/SHM
        # files briefly after connection close.
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        db_path = Path(self._tmp.name) / "test.db"
        self.app = create_app(db_path=db_path)
        self.client = TestClient(self.app)

    def test_healthz(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_professional_signup_happy_path(self) -> None:
        response = self.client.post(
            "/api/professionals/signup",
            json={
                "full_name": "Dr. Anna Vermeer",
                "role": "huisarts",
                "email": "anna.api@example.com",
                "agb_code": "01024587",
                "big_number": "12345678",
                "city": "Amsterdam",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["professional"]["verification_status"], "approved")
        self.assertEqual(body["verification"]["outcome"], "passed")
        self.assertEqual(body["professional"]["qualification"], "huisarts")
        self.assertIsNotNone(body["professional"]["onderneming_agb_code"])

    def test_professional_signup_returns_422_on_verification_failure(self) -> None:
        response = self.client.post(
            "/api/professionals/signup",
            json={
                "full_name": "Bad",
                "role": "huisarts",
                "email": "bad.api@example.com",
                "agb_code": "ZZZZZZZZ",
                "big_number": "12345678",
            },
        )
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["message"], "Professional verification failed")
        self.assertIn("professional_id", detail)

    def test_professional_signup_conflict_on_duplicate(self) -> None:
        payload = {
            "full_name": "A",
            "role": "huisarts",
            "email": "dup.api@example.com",
            "agb_code": "01010001",
            "big_number": "12345678",
        }
        first = self.client.post("/api/professionals/signup", json=payload)
        self.assertEqual(first.status_code, 201)
        second = self.client.post("/api/professionals/signup", json=payload)
        self.assertEqual(second.status_code, 409)

    def test_create_referral_end_to_end(self) -> None:
        signup = self.client.post(
            "/api/professionals/signup",
            json={
                "full_name": "Dr. Anna",
                "role": "huisarts",
                "email": "referrer@example.com",
                "agb_code": "01024500",
                "big_number": "11111111",
            },
        ).json()

        referral_payload = {
            "professional_id": signup["professional"]["id"],
            "profile": {
                "first_name": "Sofia",
                "email": "sofia.api@example.com",
                "preferred_language": "nl",
                "city": "Amsterdam",
                "neighborhood": "Oud-West",
                "social_comfort": "small_group_low_pressure",
                "preferred_group_size_min": 3,
                "preferred_group_size_max": 6,
                "cost_sensitivity": "free_or_low_cost",
                "interests": ["photography", "parks"],
                "availability": [
                    {"weekday": "sat", "start_time_local": "10:00", "end_time_local": "12:00"}
                ],
                "avoidances": ["alcohol"],
            },
            "referral_reason": "feels isolated, recently moved",
            "capture_method": "in_consult",
        }
        response = self.client.post("/api/referrals", json=referral_payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["resident"]["first_name"], "Sofia")
        self.assertEqual(body["consent"]["status"], "active")
        self.assertEqual(body["consent"]["capture_method"], "in_consult")
        self.assertEqual(body["referral"]["status"], "submitted")
        self.assertEqual(
            sorted(body["consent"]["scopes"]),
            sorted(
                [
                    "create_social_profile",
                    "use_profile_for_activity_matching",
                    "send_activity_invitations",
                    "share_limited_status_with_professional",
                ]
            ),
        )

        list_response = self.client.get(
            f"/api/professionals/{signup['professional']['id']}/referrals"
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)


if __name__ == "__main__":
    unittest.main()
