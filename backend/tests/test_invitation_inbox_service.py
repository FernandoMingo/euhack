"""Tests for the resident invitation inbox service.

These verify that sending invitations for an approved circle creates
one inbox item per resident, that the inbox content excludes
matching/fit/peer-rating data, that the email message is queued (no
real send by default), and that the audit trail is written.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import (  # noqa: E402
    ActivityRepository,
    FakeEmailClient,
    InvitationInboxService,
    OutboundEmailRepository,
    QueuedEmailClient,
    ResidentInboxRepository,
    ResidentRepository,
    connect,
    init_db,
)
from app.services import MatchingWorkflowService  # noqa: E402


def _bootstrap_circle(
    activities: ActivityRepository,
    residents: ResidentRepository,
    *,
    member_count: int,
):
    venue = activities.create_venue(
        name="Community Room",
        address="Hoofdstraat 1",
        city="Rotterdam",
    )
    activity = activities.create_activity(
        title="Photography Walk along the Maas",
        activity_type="photography_walk",
        venue_id=venue.id,
        start_at="2026-05-23T10:00:00+00:00",
        end_at="2026-05-23T11:30:00+00:00",
        capacity=member_count + 1,
        risk_level="low",
        approval_status="approved",
    )
    circle = activities.create_circle(
        activity_id=activity.id,
        status="proposed",
        fit_score=0.82,
        shared_signals_json=json.dumps(
            {
                "shared_availability": ["sat_morning"],
                "shared_interests": ["photography"],
            }
        ),
    )
    resident_ids: list[str] = []
    for idx in range(member_count):
        resident = residents.create_resident(
            first_name=f"Resident{idx}",
            email=f"resident{idx}@inbox.example.nl",
            preferred_language="English",
            city="Rotterdam",
            social_comfort="small_group_low_pressure",
            preferred_group_size_min=3,
            preferred_group_size_max=5,
            cost_sensitivity="free_or_low_cost",
        )
        activities.add_circle_member(circle_id=circle.id, resident_id=resident.id)
        resident_ids.append(resident.id)
    return activity, circle, resident_ids


class InvitationInboxServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "inbox.db"
        init_db(db_path=self.db_path)

    def test_send_invitations_creates_inbox_items_and_queued_emails(self) -> None:
        with connect(db_path=self.db_path) as conn:
            activities = ActivityRepository(conn)
            residents = ResidentRepository(conn)
            _, circle, resident_ids = _bootstrap_circle(
                activities, residents, member_count=3
            )
            conn.commit()

            invitations = MatchingWorkflowService(
                conn, email_client=QueuedEmailClient()
            ).send_invitations_for_approved_circle(
                circle_id=circle.id,
                actor_id="operator_1",
            )

            self.assertEqual(len(invitations), 3)

            inbox_repo = ResidentInboxRepository(conn)
            email_repo = OutboundEmailRepository(conn)

            for resident_id in resident_ids:
                items = inbox_repo.list_for_resident(resident_id=resident_id)
                self.assertEqual(
                    len(items),
                    1,
                    f"resident {resident_id} should have exactly one inbox item",
                )
                item = items[0]
                self.assertEqual(item.item_type, "activity_invitation")
                self.assertEqual(item.status, "unread")
                self.assertIn("Photography Walk", item.title)
                self.assertIn("Photography Walk", item.body)
                self.assertIn("Community Room", item.body)
                self.assertIn("Hoofdstraat 1", item.body)
                lower = (item.title + " " + item.body).lower()
                for forbidden in (
                    "fit",
                    "score",
                    "peer",
                    "rating",
                    "rationale",
                    "match",
                ):
                    self.assertNotIn(
                        forbidden, lower, f"inbox copy must not contain '{forbidden}'"
                    )

            queued = email_repo.list_messages(delivery_status="queued")
            self.assertEqual(len(queued), 3)
            for message in queued:
                self.assertEqual(message.provider, "queued")
                self.assertEqual(message.delivery_status, "queued")
                self.assertIsNone(message.provider_message_id)

            audit_actions = [
                row["action"]
                for row in conn.execute(
                    "SELECT action FROM audit_events ORDER BY created_at, id"
                ).fetchall()
            ]
            self.assertEqual(audit_actions.count("inbox_item.created"), 3)
            self.assertEqual(audit_actions.count("email_message.queued"), 3)
            self.assertEqual(audit_actions.count("invitation.sent"), 3)
            self.assertEqual(audit_actions.count("circle.invitations_sent"), 1)

    def test_default_email_client_does_not_actually_send(self) -> None:
        fake = FakeEmailClient()
        with connect(db_path=self.db_path) as conn:
            activities = ActivityRepository(conn)
            residents = ResidentRepository(conn)
            _, circle, _ = _bootstrap_circle(activities, residents, member_count=2)
            conn.commit()

            MatchingWorkflowService(
                conn, email_client=fake
            ).send_invitations_for_approved_circle(circle_id=circle.id)

            self.assertEqual(len(fake.sent_messages), 2)
            self.assertEqual(
                {msg.to_email for msg in fake.sent_messages},
                {"resident0@inbox.example.nl", "resident1@inbox.example.nl"},
            )
            for message in fake.sent_messages:
                self.assertIn("Photography Walk", message.subject)
                lower = message.body.lower() + " " + message.subject.lower()
                self.assertTrue(
                    any(
                        phrase in lower
                        for phrase in (
                            "no pressure",
                            "no commitment",
                            "low-key",
                            "gentle",
                        )
                    ),
                    msg=f"email copy should read as relaxed: {message.body!r}",
                )

            queued_count = conn.execute(
                "SELECT COUNT(*) FROM outbound_email_messages WHERE delivery_status = 'queued'"
            ).fetchone()[0]
            self.assertEqual(queued_count, 2)
            sent_count = conn.execute(
                "SELECT COUNT(*) FROM outbound_email_messages WHERE delivery_status = 'sent'"
            ).fetchone()[0]
            self.assertEqual(sent_count, 0)

    def test_inbox_metadata_only_contains_privacy_safe_fields(self) -> None:
        with connect(db_path=self.db_path) as conn:
            activities = ActivityRepository(conn)
            residents = ResidentRepository(conn)
            _, circle, resident_ids = _bootstrap_circle(
                activities, residents, member_count=2
            )
            conn.commit()

            MatchingWorkflowService(conn).send_invitations_for_approved_circle(
                circle_id=circle.id
            )

            inbox_repo = ResidentInboxRepository(conn)
            for resident_id in resident_ids:
                item = inbox_repo.list_for_resident(resident_id=resident_id)[0]
                metadata = json.loads(item.metadata_json)
                self.assertEqual(
                    set(metadata.keys()),
                    {
                        "invitation_id",
                        "activity_id",
                        "circle_id",
                        "activity_title",
                        "activity_start_at",
                        "activity_end_at",
                        "venue_name",
                        "venue_address",
                        "venue_city",
                    },
                )

    def test_inbox_state_transitions_read_and_archive(self) -> None:
        with connect(db_path=self.db_path) as conn:
            activities = ActivityRepository(conn)
            residents = ResidentRepository(conn)
            _, circle, resident_ids = _bootstrap_circle(
                activities, residents, member_count=1
            )
            conn.commit()

            MatchingWorkflowService(conn).send_invitations_for_approved_circle(
                circle_id=circle.id
            )

            service = InvitationInboxService(conn)
            item = ResidentInboxRepository(conn).list_for_resident(
                resident_id=resident_ids[0]
            )[0]
            self.assertIsNone(item.read_at)

            read_item = service.mark_inbox_item_read(item_id=item.id)
            self.assertEqual(read_item.status, "read")
            self.assertIsNotNone(read_item.read_at)

            archived = service.archive_inbox_item(item_id=item.id)
            self.assertEqual(archived.status, "archived")
            self.assertIsNotNone(archived.archived_at)

    def test_operator_mark_sent_writes_audit_and_updates_status(self) -> None:
        with connect(db_path=self.db_path) as conn:
            activities = ActivityRepository(conn)
            residents = ResidentRepository(conn)
            _, circle, _ = _bootstrap_circle(activities, residents, member_count=1)
            conn.commit()

            MatchingWorkflowService(conn).send_invitations_for_approved_circle(
                circle_id=circle.id
            )
            email_repo = OutboundEmailRepository(conn)
            queued = email_repo.list_messages(delivery_status="queued")
            self.assertEqual(len(queued), 1)
            message_id = queued[0].id

            updated = InvitationInboxService(conn).mark_email_sent(
                message_id=message_id,
                provider_message_id="prov-abc-123",
                actor_id="operator_2",
            )
            self.assertEqual(updated.delivery_status, "sent")
            self.assertEqual(updated.provider_message_id, "prov-abc-123")
            self.assertIsNotNone(updated.sent_at)

            sent_audit = conn.execute(
                """
                SELECT COUNT(*) FROM audit_events
                WHERE action = 'email_message.sent' AND entity_id = ?
                """,
                (message_id,),
            ).fetchone()[0]
            self.assertEqual(sent_audit, 1)


if __name__ == "__main__":
    unittest.main()
