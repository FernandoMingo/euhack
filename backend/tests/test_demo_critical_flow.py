"""Critical-path tests for the hackathon demo dataset (Sofia flow).

Exercises Fernando's API surface against ``seed_demo`` data:

  - Resident profile + preference writes (no bulk PATCH shim)
  - Privacy-safe invitation inbox (``resident_inbox_items``)
  - Demo inbox alias (``/api/demo/residents/{id}/inbox``)
  - Demo check-in + circle reveal
  - Activity template catalog
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import create_app  # noqa: E402
from app.dataclasses import Invitation  # noqa: E402
from app.db import connect  # noqa: E402
from app.repositories.base import parse_dt  # noqa: E402
from app.seed import seed_activity_templates  # noqa: E402
from app.services import InvitationInboxService  # noqa: E402
from seed_demo import seed  # noqa: E402

SOFIA_ID = "sofia-001"
PHOTO_WALK_ACTIVITY_ID = "act-photo-walk"
EXPECTED_INBOX_TITLES = {
    "Calm Photography Walk",
    "Quiet Museum Morning",
    "Evening Board Games",
    "Slow Coffee & Sketching",
}
_FORBIDDEN_INBOX_TOKENS = ("fit_score", "peer", "rating", "score")


def _backfill_sofia_inbox(db_path: Path) -> None:
    """Create inbox items for seed invitations (seed only writes ``invitations`` rows)."""
    with connect(db_path=db_path) as conn:
        service = InvitationInboxService(conn)
        rows = conn.execute(
            "SELECT * FROM invitations WHERE resident_id = ?",
            (SOFIA_ID,),
        ).fetchall()
        for row in rows:
            exists = conn.execute(
                "SELECT 1 FROM resident_inbox_items WHERE invitation_id = ?",
                (row["id"],),
            ).fetchone()
            if exists:
                continue
            invitation = Invitation(
                id=row["id"],
                circle_id=row["circle_id"],
                activity_id=row["activity_id"],
                resident_id=row["resident_id"],
                status=row["status"],
                companion_pass_used=bool(row["companion_pass_used"]),
                sent_at=parse_dt(row["sent_at"]),  # type: ignore[arg-type]
                responded_at=parse_dt(row["responded_at"])
                if row["responded_at"]
                else None,
            )
            service.create_artifacts_for_invitation(invitation=invitation)
        conn.commit()


class DemoCriticalFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "demo.db"
        self.app = create_app(db_path=self.db_path)
        seed(self.db_path)
        with connect(db_path=self.db_path) as conn:
            seed_activity_templates(conn)
            conn.commit()
        _backfill_sofia_inbox(self.db_path)
        self.client = TestClient(self.app)

    def test_seeded_resident_profile(self) -> None:
        response = self.client.get(f"/api/residents/{SOFIA_ID}")
        self.assertEqual(response.status_code, 200, response.text)
        resident = response.json()
        self.assertEqual(resident["first_name"], "Sofia")
        self.assertEqual(resident["status"], "active")
        self.assertEqual(resident["city"], "Amsterdam")
        self.assertEqual(resident["neighborhood"], "Oud-West")

    def test_add_preference_does_not_change_identity(self) -> None:
        response = self.client.post(
            f"/api/residents/{SOFIA_ID}/preferences",
            json={"preference_type": "interest", "value": "theme:photography"},
        )
        self.assertEqual(response.status_code, 201, response.text)

        profile = self.client.get(f"/api/residents/{SOFIA_ID}")
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["first_name"], "Sofia")

    def test_resident_inbox_lists_seeded_activity_invitations(self) -> None:
        response = self.client.get(f"/api/residents/{SOFIA_ID}/inbox")
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()
        self.assertGreaterEqual(len(items), 4)
        combined = " ".join(f"{item['title']} {item['body']}" for item in items)
        for activity_title in EXPECTED_INBOX_TITLES:
            self.assertIn(activity_title, combined)
        for item in items:
            self.assertEqual(item["status"], "unread")
            self.assertEqual(item["item_type"], "activity_invitation")
            self.assertEqual(item["resident_id"], SOFIA_ID)

    def test_inbox_items_are_privacy_safe(self) -> None:
        items = self.client.get(f"/api/residents/{SOFIA_ID}/inbox").json()
        for item in items:
            blob = f"{item['title']} {item['body']}".lower()
            for token in _FORBIDDEN_INBOX_TOKENS:
                self.assertNotIn(token, blob)
            metadata = item.get("metadata") or {}
            for key in metadata:
                self.assertNotIn("score", key.lower())
                self.assertNotIn("rating", key.lower())

    def test_demo_inbox_alias_matches_canonical_inbox(self) -> None:
        canonical = self.client.get(f"/api/residents/{SOFIA_ID}/inbox")
        demo = self.client.get(f"/api/demo/residents/{SOFIA_ID}/inbox")
        self.assertEqual(canonical.status_code, 200, canonical.text)
        self.assertEqual(demo.status_code, 200, demo.text)
        self.assertEqual(canonical.json(), demo.json())

    def test_mark_inbox_item_read(self) -> None:
        items = self.client.get(f"/api/residents/{SOFIA_ID}/inbox").json()
        item_id = items[0]["id"]
        read = self.client.post(f"/api/residents/{SOFIA_ID}/inbox/{item_id}/read")
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual(read.json()["status"], "read")

    def test_demo_check_in_unlocks_circle_reveal(self) -> None:
        locked = self.client.get(
            f"/api/demo/activities/{PHOTO_WALK_ACTIVITY_ID}/circle-reveal",
            params={"resident_id": SOFIA_ID},
        )
        self.assertEqual(locked.status_code, 200, locked.text)
        self.assertTrue(locked.json()["locked"])

        check_in = self.client.post(
            f"/api/demo/activities/{PHOTO_WALK_ACTIVITY_ID}/check-in",
            json={"resident_id": SOFIA_ID},
        )
        self.assertEqual(check_in.status_code, 200, check_in.text)

        reveal = self.client.get(
            f"/api/demo/activities/{PHOTO_WALK_ACTIVITY_ID}/circle-reveal",
            params={"resident_id": SOFIA_ID},
        )
        self.assertEqual(reveal.status_code, 200, reveal.text)
        body = reveal.json()
        self.assertFalse(body["locked"])
        self.assertGreater(len(body["attendees"]), 0)
        for attendee in body["attendees"]:
            self.assertTrue(attendee["first_name"])
            self.assertNotEqual(attendee["first_name"], "Sofia")

    def test_activity_template_catalog_available(self) -> None:
        response = self.client.get("/api/templates/photography_walk")
        self.assertEqual(response.status_code, 200, response.text)
        template = response.json()
        self.assertEqual(template["code"], "photography_walk")

        families = self.client.get("/api/templates/families")
        self.assertEqual(families.status_code, 200, families.text)
        self.assertGreater(len(families.json()), 0)

    def test_demo_operator_inbox_shape(self) -> None:
        response = self.client.get("/api/demo/operator/inbox")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("pending_referrals", body)
        self.assertIn("proposals", body)
        self.assertIsInstance(body["pending_referrals"], list)
        self.assertIsInstance(body["proposals"], list)


if __name__ == "__main__":
    unittest.main()
