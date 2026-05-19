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

import html as _html
import json
import logging
import os
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


_DEFAULT_APP_BASE_URL = "http://127.0.0.1:3001"
_DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def _app_base_url() -> str:
    """Return the canonical user-facing app URL (no trailing slash).

    Configured via the ``APP_BASE_URL`` env var. Falls back to the local
    Next.js dev server. Used to build the "View activity in the app" link
    in invitation emails.
    """
    return (os.environ.get("APP_BASE_URL") or _DEFAULT_APP_BASE_URL).rstrip("/")


def _api_base_url() -> str:
    """Return the canonical backend URL (no trailing slash).

    Configured via the ``API_BASE_URL`` env var. Falls back to the local
    FastAPI dev server. Used to build the Accept / Decline click links
    in invitation emails (those live on the backend so a single GET can
    flip the status server-side).
    """
    return (os.environ.get("API_BASE_URL") or _DEFAULT_API_BASE_URL).rstrip("/")


@dataclass(slots=True, frozen=True)
class _ActionUrls:
    accept: str
    decline: str
    bring_companion: str
    view_activity: str


def _build_action_urls(*, invitation_id: str, activity_id: str) -> _ActionUrls:
    api = _api_base_url()
    app = _app_base_url()
    return _ActionUrls(
        accept=f"{api}/r/invitations/{invitation_id}/accept",
        decline=f"{api}/r/invitations/{invitation_id}/decline",
        bring_companion=f"{api}/r/invitations/{invitation_id}/accept-with-companion",
        view_activity=f"{app}/inbox?activity_id={activity_id}",
    )


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
        urls = _build_action_urls(
            invitation_id=invitation.id, activity_id=invitation.activity_id
        )
        member_count = len(
            self.activities.list_circle_members(circle_id=invitation.circle_id)
        )
        email_body = self._build_email_body(
            resident=resident,
            activity=activity,
            venue=venue,
            urls=urls,
            member_count=member_count,
        )
        email_html = self._build_email_html(
            resident=resident,
            activity=activity,
            venue=venue,
            urls=urls,
            member_count=member_count,
        )
        payload = EmailMessagePayload(
            to_email=resident.email,
            subject=subject,
            body=email_body,
            resident_id=resident.id,
            html_body=email_html,
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
        try:
            day_part = f"{weekday}, {start.strftime('%B %-d')}".strip(", ")
        except ValueError:  # Windows: %-d unsupported
            day_part = f"{weekday}, {start.strftime('%B %d').replace(' 0', ' ')}".strip(", ")
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
        return f"You’re invited: {activity.title}"

    def _resident_greeting_name(self, resident: Resident) -> str:
        name = (resident.first_name or "").strip()
        return name or "there"

    def _format_location(self, venue: Venue | None) -> str | None:
        if venue is None:
            return None
        parts = [venue.name]
        if venue.address:
            parts.append(venue.address)
        elif venue.city:
            parts.append(venue.city)
        return ", ".join(p for p in parts if p)

    def _format_people_count(self, member_count: int) -> str:
        if member_count <= 1:
            return "A small circle is forming"
        return f"{member_count} people in this circle"

    def _build_email_body(
        self,
        *,
        resident: Resident,
        activity: Activity,
        venue: Venue | None,
        urls: _ActionUrls,
        member_count: int,
    ) -> str:
        """Plain-text invitation email fallback.

        The HTML alternative carries the same content; keep this readable
        in clients that strip HTML (and in providers' preview panes).
        """
        greeting = self._resident_greeting_name(resident)
        location = self._format_location(venue)
        people = self._format_people_count(member_count)
        lines = [
            f"Hi {greeting},",
            "",
            "You are invited to an activity:",
            "",
            activity.title,
        ]
        if location:
            lines.extend(["", f"Where: {location}"])
        lines.extend(["", f"Who: {people}"])
        lines.extend(
            [
                "",
                "This activity was selected for you by CivicCircles.",
                "",
                f"Yes, count me in: {urls.accept}",
                f"Not this time: {urls.decline}",
                f"Bring someone I trust: {urls.bring_companion}",
                "",
                f"View activity in the app: {urls.view_activity}",
                "",
                "Warmly,",
                "The CivicCircles team",
            ]
        )
        return "\n".join(lines)

    def _build_email_html(
        self,
        *,
        resident: Resident,
        activity: Activity,
        venue: Venue | None,
        urls: _ActionUrls,
        member_count: int,
    ) -> str:
        """Calm, minimal HTML email (inline styles + tables for client compat)."""
        greeting = _html.escape(self._resident_greeting_name(resident))
        title = _html.escape(activity.title)
        accept = _html.escape(urls.accept, quote=True)
        decline = _html.escape(urls.decline, quote=True)
        companion = _html.escape(urls.bring_companion, quote=True)
        view = _html.escape(urls.view_activity, quote=True)
        location_text = self._format_location(venue)
        location_row = ""
        if location_text:
            location_row = f"""
            <tr>
              <td style="padding:0 32px 6px 32px;font-size:14px;line-height:1.6;color:#4a564a;">
                <span style="color:#7d8a7d;text-transform:uppercase;letter-spacing:0.06em;font-size:11px;">Where</span><br />
                {_html.escape(location_text)}
              </td>
            </tr>"""
        people_text = _html.escape(self._format_people_count(member_count))
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>You're invited</title>
  </head>
  <body style="margin:0;padding:0;background:#f7f5f1;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#2f3a2f;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f7f5f1;">
      <tr>
        <td align="center" style="padding:32px 16px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:540px;background:#ffffff;border-radius:18px;border:1px solid #e4e0d8;box-shadow:0 2px 8px rgba(60,55,40,0.04);">
            <tr>
              <td style="padding:32px 32px 8px 32px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#7d8a7d;">
                CivicCircles
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 8px 32px;font-size:17px;line-height:1.5;color:#2f3a2f;">
                Hi {greeting},
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 4px 32px;font-size:15px;line-height:1.6;color:#4a564a;">
                You are invited to an activity:
              </td>
            </tr>
            <tr>
              <td style="padding:4px 32px 14px 32px;font-size:22px;line-height:1.35;font-weight:500;color:#2f3a2f;">
                {title}
              </td>
            </tr>{location_row}
            <tr>
              <td style="padding:0 32px 18px 32px;font-size:14px;line-height:1.6;color:#4a564a;">
                <span style="color:#7d8a7d;text-transform:uppercase;letter-spacing:0.06em;font-size:11px;">Who</span><br />
                {people_text}
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 20px 32px;font-size:14px;line-height:1.6;color:#6b7a6b;">
                This activity was selected for you by CivicCircles. There's no
                pressure — only say yes if it feels right.
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 8px 32px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="padding-bottom:10px;">
                      <a href="{accept}"
                         style="display:inline-block;padding:12px 22px;border-radius:999px;background:#cfe3c8;color:#1e3a1e;font-size:15px;font-weight:500;text-decoration:none;border:1px solid #a8c8a0;">
                        Yes, count me in
                      </a>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding-bottom:10px;">
                      <a href="{companion}"
                         style="display:inline-block;padding:12px 22px;border-radius:999px;background:#e4ecf5;color:#23415e;font-size:15px;font-weight:500;text-decoration:none;border:1px solid #b8cbe0;">
                        Bring someone I trust
                      </a>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <a href="{decline}"
                         style="display:inline-block;padding:12px 22px;border-radius:999px;background:#f3efe6;color:#5b6258;font-size:15px;font-weight:500;text-decoration:none;border:1px solid #ddd6c6;">
                        Not this time
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 32px 32px 32px;font-size:14px;line-height:1.6;">
                <a href="{view}" style="color:#3e6b3e;text-decoration:underline;">
                  View activity in the app
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 24px 32px;font-size:12px;color:#9aa39a;line-height:1.5;border-top:1px solid #efece4;padding-top:18px;">
                Sent with care by CivicCircles. You can withdraw at any time.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

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
