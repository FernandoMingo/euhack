from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def deterministic_or_random(prefix: str, value: str | None = None) -> str:
    if value:
        return value
    return f"{prefix}_{uuid4().hex[:8]}"
