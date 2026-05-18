from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402


class InvitationsConsentsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(db_path=Path(self._tmp.name) / "test.db")
        self.client = TestClient(self.app)

        signup = self.client.post(
            "/api/professionals/signup",
            json={
                "full_name": "Doc",
                "role": "huisarts",
                "email": "doc@invites.example.nl",
                "agb_code": "01024510",
                "big_number": "12345678",
            },
        ).json()
        ref = self.client.post(
            "/api/referrals",
            json={
                "professional_id": signup["professional"]["id"],
                "profile": {
                    "first_name": "Sofia",
                    "email": "sofia@invites.example.nl",
                    "preferred_language": "nl",
                    "city": "Amsterdam",
                    "social_comfort": "small_group_low_pressure",
                    "preferred_group_size_min": 3,
                    "preferred_group_size_max": 6,
                    "cost_sensitivity": "free_or_low_cost",
                },
            },
        ).json()
        self.resident_id = ref["resident"]["id"]
        self.consent_id = ref["consent"]["id"]
        self.referral_id = ref["referral"]["id"]

        venue = self.client.post(
            "/api/venues",
            json={"name": "V", "address": "A", "city": "Amsterdam"},
        ).json()
        activity = self.client.post(
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
        ).json()
        circle = self.client.post(
            f"/api/activities/{activity['id']}/circles",
            json={},
        ).json()
        self.activity_id = activity["id"]
        self.circle_id = circle["id"]

    def test_invitation_accept_and_decline(self) -> None:
        inv = self.client.post(
            "/api/invitations",
            json={
                "circle_id": self.circle_id,
                "activity_id": self.activity_id,
                "resident_id": self.resident_id,
            },
        ).json()
        self.assertEqual(inv["status"], "sent")

        accepted = self.client.post(
            f"/api/invitations/{inv['id']}/accept",
            json={"companion_pass_used": True},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertTrue(accepted.json()["companion_pass_used"])

        declined = self.client.post(f"/api/invitations/{inv['id']}/decline")
        self.assertEqual(declined.status_code, 200)
        self.assertEqual(declined.json()["status"], "declined")

    def test_get_invitation_404(self) -> None:
        r = self.client.get("/api/invitations/missing")
        self.assertEqual(r.status_code, 404)

    def test_consent_get_and_revoke(self) -> None:
        r = self.client.get(f"/api/consents/{self.consent_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "active")

        rev = self.client.post(f"/api/consents/{self.consent_id}/revoke")
        self.assertEqual(rev.status_code, 200)
        self.assertEqual(rev.json()["status"], "revoked")

    def test_referral_status_patch(self) -> None:
        r = self.client.patch(
            f"/api/referrals/{self.referral_id}/status",
            json={"status": "closed"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "closed")


if __name__ == "__main__":
    unittest.main()
