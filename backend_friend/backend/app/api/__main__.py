"""Run the onboarding API: ``python -m app.api``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from app.api.main import create_app
from app.db import DEFAULT_DB_PATH
from app.logging_config import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CivicCircles onboarding API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    configure_logging(args.log_level)
    logging.getLogger(__name__).info("Starting onboarding API on %s:%d", args.host, args.port)

    app = create_app(db_path=args.db_path)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
