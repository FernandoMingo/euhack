"""Repository for outbound email delivery queue / audit.

Every invitation that reaches the resident inbox also queues an
`outbound_email_messages` row. The default `EmailClient` does not send
mail and only marks the row `queued`. Real provider integrations can
flip rows to `sent` / `failed` with a `provider_message_id` or
`error_message` later; either way the table is the audit trail for
"did we attempt to email this resident, and what was the outcome?".
"""

from __future__ import annotations

from app.dataclasses import EmailDeliveryStatus, OutboundEmailMessage
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


_VALID_STATUSES: tuple[EmailDeliveryStatus, ...] = ("queued", "sent", "failed", "skipped")


def _row_to_message(row: object) -> OutboundEmailMessage:
    return OutboundEmailMessage(
        id=row["id"],  # type: ignore[index]
        inbox_item_id=row["inbox_item_id"],  # type: ignore[index]
        resident_id=row["resident_id"],  # type: ignore[index]
        to_email=row["to_email"],  # type: ignore[index]
        subject=row["subject"],  # type: ignore[index]
        body=row["body"],  # type: ignore[index]
        provider=row["provider"],  # type: ignore[index]
        delivery_status=row["delivery_status"],  # type: ignore[index,arg-type]
        provider_message_id=row["provider_message_id"],  # type: ignore[index]
        error_message=row["error_message"],  # type: ignore[index]
        created_at=parse_dt(row["created_at"]),  # type: ignore[index,arg-type]
        updated_at=parse_dt(row["updated_at"]),  # type: ignore[index,arg-type]
        sent_at=parse_dt(row["sent_at"]),  # type: ignore[index,arg-type]
    )


class OutboundEmailRepository(RepositoryBase):
    """SQLite-backed access to the `outbound_email_messages` table."""

    def create_message(
        self,
        *,
        resident_id: str,
        to_email: str,
        subject: str,
        body: str,
        provider: str,
        delivery_status: EmailDeliveryStatus = "queued",
        inbox_item_id: str | None = None,
        provider_message_id: str | None = None,
        error_message: str | None = None,
    ) -> OutboundEmailMessage:
        if delivery_status not in _VALID_STATUSES:
            raise ValueError(f"Unsupported delivery status {delivery_status!r}")
        message_id = new_id("email")
        now = utc_now_iso()
        sent_at = now if delivery_status == "sent" else None
        self.execute(
            """
            INSERT INTO outbound_email_messages (
                id, inbox_item_id, resident_id, to_email, subject, body,
                provider, delivery_status, provider_message_id,
                error_message, created_at, updated_at, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                inbox_item_id,
                resident_id,
                to_email,
                subject,
                body,
                provider,
                delivery_status,
                provider_message_id,
                error_message,
                now,
                now,
                sent_at,
            ),
        )
        return self.get_required(message_id)

    def get_message(self, message_id: str) -> OutboundEmailMessage | None:
        row = self.fetchone(
            "SELECT * FROM outbound_email_messages WHERE id = ?", (message_id,)
        )
        if row is None:
            return None
        return _row_to_message(row)

    def get_required(self, message_id: str) -> OutboundEmailMessage:
        message = self.get_message(message_id)
        if message is None:
            raise ValueError(f"Outbound email message {message_id} not found")
        return message

    def list_messages(
        self,
        *,
        delivery_status: EmailDeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[OutboundEmailMessage]:
        if delivery_status is None:
            rows = self.fetchall(
                """
                SELECT * FROM outbound_email_messages
                ORDER BY created_at DESC, id
                LIMIT ?
                """,
                (limit,),
            )
        else:
            rows = self.fetchall(
                """
                SELECT * FROM outbound_email_messages
                WHERE delivery_status = ?
                ORDER BY created_at DESC, id
                LIMIT ?
                """,
                (delivery_status, limit),
            )
        return [_row_to_message(row) for row in rows]

    def mark_sent(
        self,
        *,
        message_id: str,
        provider_message_id: str | None = None,
    ) -> OutboundEmailMessage:
        now = utc_now_iso()
        self.execute(
            """
            UPDATE outbound_email_messages
            SET delivery_status = 'sent',
                provider_message_id = COALESCE(?, provider_message_id),
                sent_at = COALESCE(sent_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (provider_message_id, now, now, message_id),
        )
        return self.get_required(message_id)

    def mark_failed(
        self,
        *,
        message_id: str,
        error_message: str,
    ) -> OutboundEmailMessage:
        now = utc_now_iso()
        self.execute(
            """
            UPDATE outbound_email_messages
            SET delivery_status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (error_message, now, message_id),
        )
        return self.get_required(message_id)
