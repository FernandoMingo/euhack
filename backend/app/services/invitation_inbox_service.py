"""Service that turns an invitation into a resident inbox item + queued email.

The matching workflow service owns the lifecycle (`invitations` row,
circle status, send-invitations audit). This service owns the
resident-facing surface that hangs off each invitation:

  * a `resident_inbox_items` row with privacy-safe English copy, and
  * an `outbound_email_messages` row that lives behind a pluggable
    `EmailClient`. The default client never sends a real email.

Both writes are audit-logged. The service is intentionally
synchronous: it does its work inside the caller's transaction so
"invitation sent" / "inbox created" / "email queued" stay consistent.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from sqlite3 import Connection

from app.dataclasses import (
    Activity,
    Invitation,
    OutboundEmailMessage,
    Resident,
    ResidentInboxItem,
    Venue,
)
from app.repositories import (
    ActivityRepository,
    OutboundEmailRepository,
    ResidentInboxRepository,
    ResidentRepository,
)
from app.repositories.base import new_id, utc_now_iso
from app.services.email_client import (
    EmailClient,
    EmailMessagePayload,
    QueuedEmailClient,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class InvitationInboxArtifacts:
    """Artifacts created for a single invitation."""

    inbox_item: ResidentInboxItem
    email_message: OutboundEmailMessage


_WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


class InvitationInboxService:
    """Resident invitation inbox + email queue."""

    def __init__(
        self,
        conn: Connection,
        *,
        email_client: EmailClient | None = None,
    ) -> None:
        self.conn = conn
        self.activities = ActivityRepository(conn)
        self.residents = ResidentRepository(conn)
        self.inbox = ResidentInboxRepository(conn)
        self.emails = OutboundEmailRepository(conn)
        self.email_client: EmailClient = email_client or QueuedEmailClient()

    def create_artifacts_for_invitation(
        self,
        *,
        invitation: Invitation,
        actor_id: str | None = None,
    ) -> InvitationInboxArtifacts:
        """Persist a resident inbox item + queue an email for an invitation."""

        resident = self.residents.get_resident(invitation.resident_id)
        if resident is None:
            raise ValueError(
                f"Resident {invitation.resident_id} not found for invitation"
            )
        activity = self.activities.get_activity(invitation.activity_id)
        if activity is None:
            raise ValueError(
                f"Activity {invitation.activity_id} not found for invitation"
            )
        venue = self._fetch_venue(activity.venue_id)

        title = self._build_title(activity)
        body = self._build_body(resident=resident, activity=activity, venue=venue)
        metadata = self._build_metadata(
            invitation=invitation, activity=activity, venue=venue
        )

        inbox_item = self.inbox.create_item(
            resident_id=invitation.resident_id,
            item_type="activity_invitation",
            title=title,
            body=body,
            invitation_id=invitation.id,
            activity_id=invitation.activity_id,
            circle_id=invitation.circle_id,
            metadata_json=json.dumps(metadata, sort_keys=True),
        )
        self._add_audit_event(
            actor_type="system",
            actor_id=actor_id,
            action="inbox_item.created",
            entity_type="resident_inbox_item",
            entity_id=inbox_item.id,
            metadata={
                "resident_id": invitation.resident_id,
                "invitation_id": invitation.id,
                "activity_id": invitation.activity_id,
                "circle_id": invitation.circle_id,
            },
        )

        subject = self._build_email_subject(activity)
        email_body = self._build_email_body(
            resident=resident,
            activity=activity,
            venue=venue,
        )
        payload = EmailMessagePayload(
            to_email=resident.email,
            subject=subject,
            body=email_body,
            resident_id=resident.id,
        )

        try:
            result = self.email_client.send(payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "EmailClient.send raised; queueing message as failed",
                extra={"resident_id": resident.id},
            )
            email_message = self.emails.create_message(
                resident_id=resident.id,
                to_email=resident.email,
                subject=subject,
                body=email_body,
                provider=getattr(self.email_client, "provider_name", "unknown"),
                delivery_status="failed",
                inbox_item_id=inbox_item.id,
                error_message=str(exc),
            )
            self._add_audit_event(
                actor_type="system",
                actor_id=actor_id,
                action="email_message.failed",
                entity_type="outbound_email_message",
                entity_id=email_message.id,
                metadata={
                    "resident_id": resident.id,
                    "inbox_item_id": inbox_item.id,
                    "error": str(exc),
                },
            )
            return InvitationInboxArtifacts(
                inbox_item=inbox_item, email_message=email_message
            )

        email_message = self.emails.create_message(
            resident_id=resident.id,
            to_email=resident.email,
            subject=subject,
            body=email_body,
            provider=result.provider,
            delivery_status=result.status,  # type: ignore[arg-type]
            inbox_item_id=inbox_item.id,
            provider_message_id=result.provider_message_id,
            error_message=result.error_message,
        )

        if result.status == "sent":
            audit_action = "email_message.sent"
        elif result.status == "failed":
            audit_action = "email_message.failed"
        else:
            audit_action = "email_message.queued"
        self._add_audit_event(
            actor_type="system",
            actor_id=actor_id,
            action=audit_action,
            entity_type="outbound_email_message",
            entity_id=email_message.id,
            metadata={
                "resident_id": resident.id,
                "inbox_item_id": inbox_item.id,
                "provider": result.provider,
                "delivery_status": result.status,
            },
        )
        return InvitationInboxArtifacts(
            inbox_item=inbox_item, email_message=email_message
        )

    def mark_inbox_item_read(self, *, item_id: str) -> ResidentInboxItem:
        return self.inbox.update_status(item_id=item_id, new_status="read")

    def archive_inbox_item(self, *, item_id: str) -> ResidentInboxItem:
        return self.inbox.update_status(item_id=item_id, new_status="archived")

    def mark_email_sent(
        self,
        *,
        message_id: str,
        provider_message_id: str | None = None,
        actor_id: str | None = None,
    ) -> OutboundEmailMessage:
        message = self.emails.mark_sent(
            message_id=message_id, provider_message_id=provider_message_id
        )
        self._add_audit_event(
            actor_type="operator",
            actor_id=actor_id,
            action="email_message.sent",
            entity_type="outbound_email_message",
            entity_id=message.id,
            metadata={
                "resident_id": message.resident_id,
                "provider": message.provider,
                "provider_message_id": message.provider_message_id,
            },
        )
        self.conn.commit()
        return message

    def _fetch_venue(self, venue_id: str) -> Venue | None:
        row = self.conn.execute(
            "SELECT * FROM venues WHERE id = ?", (venue_id,)
        ).fetchone()
        if row is None:
            return None
        from app.repositories.base import parse_dt

        return Venue(
            id=row["id"],
            name=row["name"],
            address=row["address"],
            city=row["city"],
            lat=row["lat"],
            lng=row["lng"],
            created_at=parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    def _build_title(self, activity: Activity) -> str:
        return f"You're invited: {activity.title}"

    def _build_when_phrase(self, activity: Activity) -> str:
        start = activity.start_at
        weekday = _WEEKDAY_NAMES.get(start.weekday(), "")
        day_part = f"{weekday}, {start.strftime('%B %-d')}".strip(", ")
        try:
            time_part = start.strftime("%-H:%M")
        except ValueError:  # pragma: no cover - platform fallback
            time_part = start.strftime("%H:%M")
        return f"{day_part} at {time_part}".strip()

    def _build_body(
        self,
        *,
        resident: Resident,
        activity: Activity,
        venue: Venue | None,
    ) -> str:
        when_phrase = self._build_when_phrase(activity)
        venue_phrase = (
            f"at {venue.name}, {venue.address}" if venue is not None else ""
        )
        lines = [
            f"Hi {resident.first_name},",
            "",
            (
                f"We thought you might enjoy joining a small group for "
                f"{activity.title}."
            ),
            f"It's on {when_phrase}" + (f" {venue_phrase}." if venue_phrase else "."),
            "",
            (
                "There's no pressure — it's a relaxed gathering of a few "
                "people from your area. Come if it feels right, and let us "
                "know either way when you have a moment."
            ),
            "",
            "Warmly,",
            "The CivicCircles team",
        ]
        return "\n".join(lines)

    def _build_email_subject(self, activity: Activity) -> str:
        return f"A gentle invitation to {activity.title}"

    def _build_email_body(
        self,
        *,
        resident: Resident,
        activity: Activity,
        venue: Venue | None,
    ) -> str:
        when_phrase = self._build_when_phrase(activity)
        venue_phrase = (
            f"at {venue.name}, {venue.address}" if venue is not None else ""
        )
        lines = [
            f"Hi {resident.first_name},",
            "",
            (
                f"We'd love to invite you to a small, low-key gathering: "
                f"{activity.title}."
            ),
            f"When: {when_phrase}",
        ]
        if venue_phrase:
            lines.append(f"Where: {venue_phrase}")
        lines.extend(
            [
                "",
                (
                    "No commitment needed right now. Take your time, and only "
                    "say yes if it feels comfortable."
                ),
                (
                    "You can also reply in your CivicCircles inbox whenever "
                    "you're ready."
                ),
                "",
                "Warmly,",
                "The CivicCircles team",
            ]
        )
        return "\n".join(lines)

    def _build_metadata(
        self,
        *,
        invitation: Invitation,
        activity: Activity,
        venue: Venue | None,
    ) -> dict[str, object]:
        # Privacy-safe metadata only: identifiers + activity time/venue.
        # No fit scores, no peer ratings, no other residents' info.
        payload: dict[str, object] = {
            "invitation_id": invitation.id,
            "activity_id": invitation.activity_id,
            "circle_id": invitation.circle_id,
            "activity_title": activity.title,
            "activity_start_at": activity.start_at.isoformat(),
            "activity_end_at": activity.end_at.isoformat(),
        }
        if venue is not None:
            payload["venue_name"] = venue.name
            payload["venue_address"] = venue.address
            payload["venue_city"] = venue.city
        return payload

    def _add_audit_event(
        self,
        *,
        actor_type: str,
        action: str,
        entity_type: str,
        metadata: dict[str, object],
        actor_id: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_events (
                id, actor_type, actor_id, action, entity_type, entity_id,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("audit"),
                actor_type,
                actor_id,
                action,
                entity_type,
                entity_id,
                json.dumps(metadata, sort_keys=True),
                utc_now_iso(),
            ),
        )


__all__ = [
    "InvitationInboxArtifacts",
    "InvitationInboxService",
]
