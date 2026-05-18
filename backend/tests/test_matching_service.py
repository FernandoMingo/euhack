from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import ActivityRepository, ResidentRepository, connect, init_db  # noqa: E402
from app.services import MatchingWorkflowService  # noqa: E402


class TestMatchingWorkflowService(unittest.TestCase):
    def test_promotes_approved_circle_to_invitations_with_audit_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "workflow.db"
            init_db(db_path=db_path)
            with connect(db_path=db_path) as conn:
                activities = ActivityRepository(conn)
                residents = ResidentRepository(conn)
                venue = activities.create_venue(
                    name="Community Room",
                    address="Main Street 1",
                    city="Amsterdam",
                )
                activity = activities.create_activity(
                    title="Coffee Meetup",
                    activity_type="coffee_meetup",
                    venue_id=venue.id,
                    start_at="2026-05-23T10:00:00+00:00",
                    end_at="2026-05-23T11:00:00+00:00",
                    capacity=4,
                    risk_level="low",
                    approval_status="approved",
                )
                circle = activities.create_circle(
                    activity_id=activity.id,
                    status="proposed",
                    fit_score=0.8,
                    shared_signals_json="{}",
                )
                for idx in range(3):
                    resident = residents.create_resident(
                        first_name=f"Resident {idx}",
                        email=f"resident{idx}@example.com",
                        preferred_language="English",
                        city="Amsterdam",
                        social_comfort="small_group_low_pressure",
                        preferred_group_size_min=3,
                        preferred_group_size_max=5,
                        cost_sensitivity="free_or_low_cost",
                    )
                    activities.add_circle_member(
                        circle_id=circle.id,
                        resident_id=resident.id,
                    )
                conn.commit()

                service = MatchingWorkflowService(conn)
                invitations = service.send_invitations_for_approved_circle(
                    circle_id=circle.id,
                    actor_id="operator_1",
                )

                self.assertEqual(len(invitations), 3)
                circle_row = activities.get_circle(circle.id)
                self.assertEqual(circle_row.status, "invitations_sent")  # type: ignore[union-attr]
                audit_count = conn.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE entity_id = ?",
                    (circle.id,),
                ).fetchone()[0]
                self.assertEqual(audit_count, 1)
                invite_count = conn.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE action = 'invitation.sent'",
                ).fetchone()[0]
                self.assertEqual(invite_count, 3)


if __name__ == "__main__":
    unittest.main()
