from __future__ import annotations

from app.dataclasses import (
    Activity,
    AttendanceEvent,
    Circle,
    CircleMember,
    Host,
    Invitation,
    ResidentFeedback,
    Venue,
)
from app.repositories.base import RepositoryBase, new_id, parse_dt, to_bool, utc_now_iso


class ActivityRepository(RepositoryBase):
    def create_venue(self, *, name: str, address: str, city: str, lat: float | None = None, lng: float | None = None) -> Venue:
        venue_id = new_id("venue")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO venues (id, name, address, city, lat, lng, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (venue_id, name, address, city, lat, lng, now, now),
        )
        return Venue(
            id=venue_id,
            name=name,
            address=address,
            city=city,
            lat=lat,
            lng=lng,
            created_at=parse_dt(now),  # type: ignore[arg-type]
            updated_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def create_host(self, *, full_name: str, host_type: str, contact_email: str | None = None) -> Host:
        host_id = new_id("host")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO hosts (id, full_name, contact_email, host_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (host_id, full_name, contact_email, host_type, now, now),
        )
        return Host(
            id=host_id,
            full_name=full_name,
            contact_email=contact_email,
            host_type=host_type,  # type: ignore[arg-type]
            created_at=parse_dt(now),  # type: ignore[arg-type]
            updated_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def create_activity(
        self,
        *,
        title: str,
        activity_type: str,
        venue_id: str,
        start_at: str,
        end_at: str,
        capacity: int,
        risk_level: str,
        approval_status: str,
        host_id: str | None = None,
        cost_cents: int = 0,
    ) -> Activity:
        activity_id = new_id("activity")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO activities (
                id, title, activity_type, venue_id, host_id, start_at, end_at, capacity,
                cost_cents, risk_level, approval_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                activity_id,
                title,
                activity_type,
                venue_id,
                host_id,
                start_at,
                end_at,
                capacity,
                cost_cents,
                risk_level,
                approval_status,
                now,
                now,
            ),
        )
        return self.get_activity(activity_id)  # type: ignore[return-value]

    def get_activity(self, activity_id: str) -> Activity | None:
        row = self.fetchone("SELECT * FROM activities WHERE id = ?", (activity_id,))
        if row is None:
            return None
        return Activity(
            id=row["id"],
            title=row["title"],
            activity_type=row["activity_type"],
            venue_id=row["venue_id"],
            host_id=row["host_id"],
            start_at=parse_dt(row["start_at"]),  # type: ignore[arg-type]
            end_at=parse_dt(row["end_at"]),  # type: ignore[arg-type]
            capacity=row["capacity"],
            cost_cents=row["cost_cents"],
            risk_level=row["risk_level"],
            approval_status=row["approval_status"],
            created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    def create_circle(
        self,
        *,
        activity_id: str | None = None,
        template_id: str | None = None,
        status: str = "proposed",
        fit_score: float | None = None,
        shared_signals_json: str = "[]",
    ) -> Circle:
        if activity_id is None and template_id is None:
            raise ValueError(
                "create_circle requires either activity_id or template_id"
            )
        circle_id = new_id("circle")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO circles (
                id, activity_id, template_id, status, fit_score,
                shared_signals_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                circle_id,
                activity_id,
                template_id,
                status,
                fit_score,
                shared_signals_json,
                now,
                now,
            ),
        )
        return Circle(
            id=circle_id,
            activity_id=activity_id,
            template_id=template_id,
            status=status,  # type: ignore[arg-type]
            fit_score=fit_score,
            shared_signals_json=shared_signals_json,
            created_at=parse_dt(now),  # type: ignore[arg-type]
            updated_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def get_circle(self, circle_id: str) -> Circle | None:
        row = self.fetchone("SELECT * FROM circles WHERE id = ?", (circle_id,))
        if row is None:
            return None
        return Circle(
            id=row["id"],
            activity_id=row["activity_id"],
            template_id=row["template_id"],
            status=row["status"],  # type: ignore[arg-type]
            fit_score=row["fit_score"],
            shared_signals_json=row["shared_signals_json"],
            created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    def list_circle_members(self, *, circle_id: str) -> list[CircleMember]:
        rows = self.fetchall(
            """
            SELECT id, circle_id, resident_id, joined_at
            FROM circle_members
            WHERE circle_id = ?
            ORDER BY joined_at, resident_id
            """,
            (circle_id,),
        )
        return [
            CircleMember(
                id=row["id"],
                circle_id=row["circle_id"],
                resident_id=row["resident_id"],
                joined_at=parse_dt(row["joined_at"]),  # type: ignore[arg-type]
            )
            for row in rows
        ]

    def add_circle_member(self, *, circle_id: str, resident_id: str) -> CircleMember:
        circle_member_id = new_id("circle_member")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO circle_members (id, circle_id, resident_id, joined_at)
            VALUES (?, ?, ?, ?)
            """,
            (circle_member_id, circle_id, resident_id, now),
        )
        return CircleMember(
            id=circle_member_id,
            circle_id=circle_id,
            resident_id=resident_id,
            joined_at=parse_dt(now),  # type: ignore[arg-type]
        )

    def create_invitation(
        self, *, circle_id: str, activity_id: str, resident_id: str, status: str = "sent"
    ) -> Invitation:
        invitation_id = new_id("invite")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO invitations (
                id, circle_id, activity_id, resident_id, status, companion_pass_used, sent_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (invitation_id, circle_id, activity_id, resident_id, status, now),
        )
        return Invitation(
            id=invitation_id,
            circle_id=circle_id,
            activity_id=activity_id,
            resident_id=resident_id,
            status=status,  # type: ignore[arg-type]
            companion_pass_used=False,
            sent_at=parse_dt(now),  # type: ignore[arg-type]
            responded_at=None,
        )

    def update_invitation_status(self, *, invitation_id: str, status: str, companion_pass_used: bool | None = None) -> None:
        now = utc_now_iso()
        if companion_pass_used is None:
            self.execute(
                "UPDATE invitations SET status = ?, responded_at = ? WHERE id = ?",
                (status, now, invitation_id),
            )
        else:
            self.execute(
                "UPDATE invitations SET status = ?, companion_pass_used = ?, responded_at = ? WHERE id = ?",
                (status, int(companion_pass_used), now, invitation_id),
            )

    def record_attendance(
        self,
        *,
        activity_id: str,
        resident_id: str,
        attendance_status: str,
        check_in_at: str | None = None,
        check_out_at: str | None = None,
    ) -> AttendanceEvent:
        attendance_id = new_id("attendance")
        self.execute(
            """
            INSERT INTO attendance_events (
                id, activity_id, resident_id, check_in_at, check_out_at, attendance_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, resident_id) DO UPDATE SET
                check_in_at = excluded.check_in_at,
                check_out_at = excluded.check_out_at,
                attendance_status = excluded.attendance_status
            """,
            (attendance_id, activity_id, resident_id, check_in_at, check_out_at, attendance_status),
        )
        row = self.fetchone(
            "SELECT * FROM attendance_events WHERE activity_id = ? AND resident_id = ?",
            (activity_id, resident_id),
        )
        return AttendanceEvent(
            id=row["id"],  # type: ignore[index]
            activity_id=activity_id,
            resident_id=resident_id,
            attendance_status=attendance_status,  # type: ignore[arg-type]
            check_in_at=parse_dt(row["check_in_at"]),  # type: ignore[index,arg-type]
            check_out_at=parse_dt(row["check_out_at"]),  # type: ignore[index,arg-type]
        )

    def add_feedback(
        self,
        *,
        activity_id: str,
        resident_id: str,
        felt_after: str | None,
        activity_fit: bool | None,
        group_comfort: bool | None,
        would_repeat: bool | None,
        safety_reported: bool = False,
        notes: str | None = None,
    ) -> ResidentFeedback:
        feedback_id = new_id("feedback")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_feedback (
                id, activity_id, resident_id, felt_after, activity_fit, group_comfort, would_repeat,
                safety_reported, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, resident_id) DO UPDATE SET
                felt_after = excluded.felt_after,
                activity_fit = excluded.activity_fit,
                group_comfort = excluded.group_comfort,
                would_repeat = excluded.would_repeat,
                safety_reported = excluded.safety_reported,
                notes = excluded.notes
            """,
            (
                feedback_id,
                activity_id,
                resident_id,
                felt_after,
                None if activity_fit is None else int(activity_fit),
                None if group_comfort is None else int(group_comfort),
                None if would_repeat is None else int(would_repeat),
                int(safety_reported),
                notes,
                now,
            ),
        )
        row = self.fetchone(
            "SELECT * FROM resident_feedback WHERE activity_id = ? AND resident_id = ?",
            (activity_id, resident_id),
        )
        return ResidentFeedback(
            id=row["id"],  # type: ignore[index]
            activity_id=activity_id,
            resident_id=resident_id,
            felt_after=row["felt_after"],  # type: ignore[index,arg-type]
            activity_fit=to_bool(row["activity_fit"]),  # type: ignore[index,arg-type]
            group_comfort=to_bool(row["group_comfort"]),  # type: ignore[index,arg-type]
            would_repeat=to_bool(row["would_repeat"]),  # type: ignore[index,arg-type]
            safety_reported=bool(row["safety_reported"]),  # type: ignore[index]
            notes=row["notes"],  # type: ignore[index]
            created_at=parse_dt(row["created_at"]),  # type: ignore[index,arg-type]
        )

