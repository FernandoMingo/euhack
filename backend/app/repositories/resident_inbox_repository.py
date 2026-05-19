"""Repository for resident-facing invitation inbox items.

Inbox items are the resident's view of an invitation. Lifecycle state
(`sent` / `accepted` / `declined`) still lives on the `invitations` row;
this table only holds the resident-facing message content plus
`read`/`archived` status so a frontend can render an inbox without
peeking at scores, peer ratings, or other residents' data.
"""

from __future__ import annotations

from app.dataclasses import InboxItemStatus, ResidentInboxItem
from app.repositories.base import RepositoryBase, new_id, parse_dt, utc_now_iso


_VALID_STATUSES: tuple[InboxItemStatus, ...] = ("unread", "read", "archived")


def _row_to_inbox_item(row: object) -> ResidentInboxItem:
    return ResidentInboxItem(
        id=row["id"],  # type: ignore[index]
        resident_id=row["resident_id"],  # type: ignore[index]
        invitation_id=row["invitation_id"],  # type: ignore[index]
        activity_id=row["activity_id"],  # type: ignore[index]
        circle_id=row["circle_id"],  # type: ignore[index]
        item_type=row["item_type"],  # type: ignore[index,arg-type]
        title=row["title"],  # type: ignore[index]
        body=row["body"],  # type: ignore[index]
        status=row["status"],  # type: ignore[index,arg-type]
        metadata_json=row["metadata_json"],  # type: ignore[index]
        created_at=parse_dt(row["created_at"]),  # type: ignore[index,arg-type]
        updated_at=parse_dt(row["updated_at"]),  # type: ignore[index,arg-type]
        read_at=parse_dt(row["read_at"]),  # type: ignore[index,arg-type]
        archived_at=parse_dt(row["archived_at"]),  # type: ignore[index,arg-type]
    )


class ResidentInboxRepository(RepositoryBase):
    """SQLite-backed access to the `resident_inbox_items` table."""

    def create_item(
        self,
        *,
        resident_id: str,
        item_type: str,
        title: str,
        body: str,
        invitation_id: str | None = None,
        activity_id: str | None = None,
        circle_id: str | None = None,
        metadata_json: str = "{}",
    ) -> ResidentInboxItem:
        item_id = new_id("inbox")
        now = utc_now_iso()
        self.execute(
            """
            INSERT INTO resident_inbox_items (
                id, resident_id, invitation_id, activity_id, circle_id,
                item_type, title, body, status, metadata_json,
                created_at, updated_at, read_at, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unread', ?, ?, ?, NULL, NULL)
            """,
            (
                item_id,
                resident_id,
                invitation_id,
                activity_id,
                circle_id,
                item_type,
                title,
                body,
                metadata_json,
                now,
                now,
            ),
        )
        return self.get_required(item_id)

    def get_item(self, item_id: str) -> ResidentInboxItem | None:
        row = self.fetchone(
            "SELECT * FROM resident_inbox_items WHERE id = ?", (item_id,)
        )
        if row is None:
            return None
        return _row_to_inbox_item(row)

    def get_required(self, item_id: str) -> ResidentInboxItem:
        item = self.get_item(item_id)
        if item is None:
            raise ValueError(f"Inbox item {item_id} not found")
        return item

    def list_for_resident(
        self,
        *,
        resident_id: str,
        status: InboxItemStatus | None = None,
        limit: int = 100,
    ) -> list[ResidentInboxItem]:
        if status is None:
            rows = self.fetchall(
                """
                SELECT * FROM resident_inbox_items
                WHERE resident_id = ?
                ORDER BY created_at DESC, id
                LIMIT ?
                """,
                (resident_id, limit),
            )
        else:
            rows = self.fetchall(
                """
                SELECT * FROM resident_inbox_items
                WHERE resident_id = ? AND status = ?
                ORDER BY created_at DESC, id
                LIMIT ?
                """,
                (resident_id, status, limit),
            )
        return [_row_to_inbox_item(row) for row in rows]

    def update_status(
        self,
        *,
        item_id: str,
        new_status: InboxItemStatus,
    ) -> ResidentInboxItem:
        if new_status not in _VALID_STATUSES:
            raise ValueError(f"Unsupported inbox status {new_status!r}")
        now = utc_now_iso()
        read_at = now if new_status == "read" else None
        archived_at = now if new_status == "archived" else None
        if new_status == "read":
            self.execute(
                """
                UPDATE resident_inbox_items
                SET status = 'read',
                    updated_at = ?,
                    read_at = COALESCE(read_at, ?)
                WHERE id = ?
                """,
                (now, read_at, item_id),
            )
        elif new_status == "archived":
            self.execute(
                """
                UPDATE resident_inbox_items
                SET status = 'archived',
                    updated_at = ?,
                    archived_at = COALESCE(archived_at, ?)
                WHERE id = ?
                """,
                (now, archived_at, item_id),
            )
        else:
            self.execute(
                """
                UPDATE resident_inbox_items
                SET status = 'unread', updated_at = ?
                WHERE id = ?
                """,
                (now, item_id),
            )
        return self.get_required(item_id)
