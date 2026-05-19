"""FastAPI tests for the resident inbox + operator email-queue endpoints."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402


class InboxApiTests(unittest.TestCase):
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
                "email": "doc@inbox.example.nl",
                "agb_code": "01024530",
                "big_number": "12345678",
            },
        ).json()
        professional_id = signup["professional"]["id"]

        def _refer(first_name: str, email: str) -> str:
            ref = self.client.post(
                "/api/referrals",
                json={
                    "professional_id": professional_id,
                    "profile": {
                        "first_name": first_name,
                        "email": email,
                        "preferred_language": "English",
                        "city": "Rotterdam",
                        "social_comfort": "small_group_low_pressure",
                        "preferred_group_size_min": 3,
                        "preferred_group_size_max": 6,
                        "cost_sensitivity": "free_or_low_cost",
                    },
                },
            )
            self.assertEqual(ref.status_code, 201, ref.text)
            return ref.json()["resident"]["id"]

        self.resident_a = _refer("Alice", "alice@inbox.example.nl")
        self.resident_b = _refer("Bob", "bob@inbox.example.nl")

        venue = self.client.post(
            "/api/venues",
            json={"name": "V", "address": "A 1", "city": "Rotterdam"},
        ).json()
        activity = self.client.post(
            "/api/activities",
            json={
                "title": "Coffee Meetup",
                "activity_type": "coffee_meetup",
                "venue_id": venue["id"],
                "start_at": "2026-06-01T10:00:00+02:00",
                "end_at": "2026-06-01T11:00:00+02:00",
                "capacity": 5,
                "risk_level": "low",
                "approval_status": "approved",
            },
        ).json()
        self.activity_id = activity["id"]
        circle = self.client.post(
            f"/api/activities/{self.activity_id}/circles",
            json={"status": "proposed", "fit_score": 0.8, "shared_signals_json": "{}"},
        ).json()
        self.circle_id = circle["id"]
        for resident_id in (self.resident_a, self.resident_b):
            r = self.client.post(
                f"/api/circles/{self.circle_id}/members",
                json={"resident_id": resident_id},
            )
            self.assertEqual(r.status_code, 201, r.text)

        promotion = self.client.post(
            f"/api/operator/circles/{self.circle_id}/send-invitations?actor_id=operator_1"
        )
        self.assertEqual(promotion.status_code, 201, promotion.text)

    def test_resident_inbox_lists_one_invitation_per_resident(self) -> None:
        for resident_id in (self.resident_a, self.resident_b):
            r = self.client.get(f"/api/residents/{resident_id}/inbox")
            self.assertEqual(r.status_code, 200, r.text)
            items = r.json()
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["status"], "unread")
            self.assertEqual(item["item_type"], "activity_invitation")
            self.assertIn("Coffee Meetup", item["title"])
            lowered = (item["title"] + item["body"]).lower()
            for forbidden in ("fit_score", "peer", "rating", "score"):
                self.assertNotIn(forbidden, lowered)

    def test_resident_inbox_isolates_residents(self) -> None:
        list_a = self.client.get(f"/api/residents/{self.resident_a}/inbox").json()
        item_id = list_a[0]["id"]
        cross = self.client.get(
            f"/api/residents/{self.resident_b}/inbox/{item_id}"
        )
        self.assertEqual(cross.status_code, 404)

    def test_read_and_archive_transitions(self) -> None:
        items = self.client.get(f"/api/residents/{self.resident_a}/inbox").json()
        item_id = items[0]["id"]

        read = self.client.post(
            f"/api/residents/{self.resident_a}/inbox/{item_id}/read"
        )
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual(read.json()["status"], "read")
        self.assertIsNotNone(read.json()["read_at"])

        archived = self.client.post(
            f"/api/residents/{self.resident_a}/inbox/{item_id}/archive"
        )
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["status"], "archived")
        self.assertIsNotNone(archived.json()["archived_at"])

        unread_only = self.client.get(
            f"/api/residents/{self.resident_a}/inbox?status=unread"
        )
        self.assertEqual(unread_only.status_code, 200, unread_only.text)
        self.assertEqual(unread_only.json(), [])

    def test_operator_email_queue_lists_queued_messages(self) -> None:
        listed = self.client.get("/api/operator/email-messages?status=queued")
        self.assertEqual(listed.status_code, 200, listed.text)
        messages = listed.json()
        self.assertEqual(len(messages), 2)
        for message in messages:
            self.assertEqual(message["delivery_status"], "queued")
            self.assertEqual(message["provider"], "queued")
            self.assertIsNone(message["sent_at"])
            self.assertIn("@inbox.example.nl", message["to_email"])

    def test_operator_can_mark_email_message_sent(self) -> None:
        messages = self.client.get("/api/operator/email-messages").json()
        message_id = messages[0]["id"]

        sent = self.client.post(
            f"/api/operator/email-messages/{message_id}/mark-sent",
            json={
                "provider_message_id": "prov-xyz-1",
                "actor_id": "operator_1",
            },
        )
        self.assertEqual(sent.status_code, 200, sent.text)
        body = sent.json()
        self.assertEqual(body["delivery_status"], "sent")
        self.assertEqual(body["provider_message_id"], "prov-xyz-1")
        self.assertIsNotNone(body["sent_at"])

        audit = self.client.get(
            f"/api/operator/audit-events?entity_id={message_id}"
        ).json()
        self.assertTrue(
            any(event["action"] == "email_message.sent" for event in audit)
        )

    def test_unknown_resident_returns_404(self) -> None:
        r = self.client.get("/api/residents/resident_does_not_exist/inbox")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
