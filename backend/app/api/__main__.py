"""Run the onboarding API: ``python -m app.api``."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from app.api.main import create_app
from app.db import DEFAULT_DB_PATH
from app.env import load_default_env_files, load_env_file
from app.logging_config import configure_logging
from app.services import OpenAIChatLLMClient, build_email_client_from_env


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CivicCircles onboarding API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional env file to load before startup. Defaults to .env/.emv in cwd.",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    configure_logging(args.log_level)
    loaded = (
        load_env_file(args.env_file)
        if args.env_file is not None
        else load_default_env_files()
    )
    logging.getLogger(__name__).info("Starting onboarding API on %s:%d", args.host, args.port)
    if loaded:
        logging.getLogger(__name__).info("Loaded %d environment value(s)", len(loaded))

    email_client = build_email_client_from_env()
    log = logging.getLogger(__name__)
    if email_client is not None:
        log.info(
            "Transactional email enabled (provider=%s).",
            getattr(email_client, "provider_name", "unknown"),
        )
    else:
        log.info(
            "Transactional email not configured; invitation outbound rows stay "
            "queued. Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD (+ EMAIL_FROM) "
            "for Gmail/SMTP, or RESEND_API_KEY + EMAIL_FROM for Resend."
        )

    app = create_app(
        db_path=args.db_path,
        llm_client=OpenAIChatLLMClient(),
        email_client=email_client,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
