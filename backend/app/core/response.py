from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def _meta(request: Request | None) -> dict[str, str]:
    request_id = "req_unknown"
    timestamp = datetime.now(timezone.utc)
    if request is not None:
        request_id = getattr(request.state, "request_id", request_id)
        timestamp = getattr(request.state, "request_timestamp", timestamp)
    return {
        "request_id": request_id,
        "timestamp": timestamp.isoformat(),
    }


def ok_response(data: Any, request: Request | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": True, "data": jsonable_encoder(data), "error": None, "meta": _meta(request)},
    )


def error_response(
    message: str,
    request: Request | None = None,
    *,
    reason_code: str = "UNKNOWN_ERROR",
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "data": None,
            "error": {"message": message, "reason_code": reason_code},
            "meta": _meta(request),
        },
    )
