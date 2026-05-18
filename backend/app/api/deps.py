from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Connection

from fastapi import Request

from app.db import connect


def get_connection(request: Request) -> Iterator[Connection]:
    """Per-request SQLite connection. Closed in the `finally` block."""
    db_path: Path = request.app.state.db_path
    conn = connect(db_path=db_path)
    try:
        yield conn
    finally:
        conn.close()
