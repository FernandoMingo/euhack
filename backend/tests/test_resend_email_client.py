"""Unit tests for Resend-backed transactional email client."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.services.email_client import (  # noqa: E402
    EmailConfigurationError,
    EmailMessagePayload,
    ResendEmailClient,
    build_email_client_from_env,
)


class ResendEmailClientTests(unittest.TestCase):
    def test_constructor_rejects_empty_key(self) -> None:
        with self.assertRaises(EmailConfigurationError):
            ResendEmailClient(api_key="", from_email="a@b.com")

    def test_constructor_rejects_empty_from(self) -> None:
        with self.assertRaises(EmailConfigurationError):
            ResendEmailClient(api_key="re_x", from_email="  ")

    def test_send_success_returns_sent_with_id(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            self.assertEqual(
                request.headers.get("authorization"),
                "Bearer re_secret",
            )
            body = json.loads(request.content.decode())
            captured["body"] = body
            return httpx.Response(200, json={"id": "re_msg_abc"})

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            resend = ResendEmailClient(
                api_key="re_secret",
                from_email="CivicCircles <from@example.com>",
                http_client=client,
            )
            result = resend.send(
                EmailMessagePayload(
                    to_email="to@example.com",
                    subject="Hello",
                    body="Plain text",
                    resident_id="resident_1",
                )
            )

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.provider, "resend")
        self.assertEqual(result.provider_message_id, "re_msg_abc")
        self.assertIsNone(result.error_message)
        self.assertIn("https://api.resend.com/emails", str(captured["url"]))
        b = captured["body"]
        assert isinstance(b, dict)
        self.assertEqual(b["from"], "CivicCircles <from@example.com>")
        self.assertEqual(b["to"], ["to@example.com"])
        self.assertEqual(b["subject"], "Hello")
        self.assertEqual(b["text"], "Plain text")

    def test_send_http_error_returns_failed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422,
                json={"message": "Invalid `from` field"},
            )

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            resend = ResendEmailClient(
                api_key="re_secret",
                from_email="bad@example.com",
                http_client=client,
            )
            result = resend.send(
                EmailMessagePayload(
                    to_email="to@example.com",
                    subject="S",
                    body="B",
                    resident_id="r1",
                )
            )

        self.assertEqual(result.status, "failed")
        self.assertIn("Invalid `from` field", result.error_message or "")

    def test_build_email_client_from_env(self) -> None:
        keys = (
            "RESEND_API_KEY",
            "EMAIL_FROM",
            "SMTP_HOST",
            "SMTP_USERNAME",
            "SMTP_PASSWORD",
            "SMTP_PORT",
            "SMTP_USE_SSL",
            "SMTP_USE_STARTTLS",
        )
        old = {k: os.environ.pop(k, None) for k in keys}
        try:
            self.assertIsNone(build_email_client_from_env())

            os.environ["RESEND_API_KEY"] = "re_test"
            os.environ["EMAIL_FROM"] = "Hi <hi@example.com>"
            client = build_email_client_from_env()
            self.assertIsInstance(client, ResendEmailClient)
            assert client is not None
            self.assertEqual(client.provider_name, "resend")
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
