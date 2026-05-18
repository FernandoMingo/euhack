from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlite3 import Connection, Row
from uuid import uuid4

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def to_bool(value: int | bool | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


class RepositoryBase:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def fetchone(self, query: str, params: tuple[object, ...] = ()) -> Row | None:
        logger.debug("fetchone query=%s params=%d", " ".join(query.split()), len(params))
        cursor = self.conn.execute(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: tuple[object, ...] = ()) -> list[Row]:
        logger.debug("fetchall query=%s params=%d", " ".join(query.split()), len(params))
        cursor = self.conn.execute(query, params)
        return list(cursor.fetchall())

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        logger.debug("execute query=%s params=%d", " ".join(query.split()), len(params))
        self.conn.execute(query, params)

