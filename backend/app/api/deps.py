from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from sqlite3 import Connection

from fastapi import Request

from app.db import connect
from app.services.llm_client import LLMClient


def get_connection(request: Request) -> Iterator[Connection]:
    """Per-request SQLite connection. Closed in the `finally` block."""
    db_path: Path = request.app.state.db_path
    conn = connect(db_path=db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_llm_client(request: Request) -> LLMClient | None:
    """Return configured LLM client, if app startup injected one."""
    return getattr(request.app.state, "llm_client", None)
