"""Unit tests for the stdlib-SMTP-backed transactional email client.

These tests inject a fake SMTP class through ``smtp_factory`` so no
network call is performed. They cover the happy path, the Gmail
convenience constructor, auth failures, and the env-based factory's
priority over the Resend client.
"""

from __future__ import annotations

import os
import smtplib
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.email_client import (  # noqa: E402
    EmailConfigurationError,
    EmailMessagePayload,
    ResendEmailClient,
    SMTPEmailClient,
    build_email_client_from_env,
)


_SMTP_ENV_KEYS = (
    "SMTP_HOST",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_PORT",
    "SMTP_USE_SSL",
    "SMTP_USE_STARTTLS",
    "EMAIL_FROM",
    "RESEND_API_KEY",
)


class _FakeSMTP:
    """Minimal stand-in for ``smtplib.SMTP`` used to capture calls."""

    instances: list["_FakeSMTP"] = []

    def __init__(
        self,
        host: str,
        port: int,
        *,
        login_should_fail: bool = False,
        send_should_fail: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.login_should_fail = login_should_fail
        self.send_should_fail = send_should_fail
        self.ehlo_count = 0
        self.starttls_called = False
        self.login_args: tuple[str, str] | None = None
        self.sent_messages: list[object] = []
        self.quit_called = False
        _FakeSMTP.instances.append(self)

    def ehlo(self) -> None:
        self.ehlo_count += 1

    def starttls(self, context=None) -> None:  # noqa: ANN001 - matches stdlib
        self.starttls_called = True

    def login(self, username: str, password: str) -> None:
        if self.login_should_fail:
            raise smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        self.login_args = (username, password)

    def send_message(self, message) -> None:  # noqa: ANN001
        if self.send_should_fail:
            raise smtplib.SMTPException("relay refused")
        self.sent_messages.append(message)

    def quit(self) -> None:
        self.quit_called = True


def _factory(**kwargs):
    def _make(host: str, port: int) -> _FakeSMTP:
        return _FakeSMTP(host, port, **kwargs)

    return _make


class SMTPEmailClientTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeSMTP.instances = []

    def test_constructor_rejects_missing_fields(self) -> None:
        with self.assertRaises(EmailConfigurationError):
            SMTPEmailClient(
                host="", username="u", password="p", from_email="f@x.com"
            )
        with self.assertRaises(EmailConfigurationError):
            SMTPEmailClient(
                host="h", username="", password="p", from_email="f@x.com"
            )
        with self.assertRaises(EmailConfigurationError):
            SMTPEmailClient(
                host="h", username="u", password="", from_email="f@x.com"
            )
        with self.assertRaises(EmailConfigurationError):
            SMTPEmailClient(
                host="h", username="u", password="p", from_email=""
            )
        with self.assertRaises(EmailConfigurationError):
            SMTPEmailClient(
                host="h",
                username="u",
                password="p",
                from_email="f@x.com",
                use_ssl=True,
                use_starttls=True,
            )

    def test_send_success_uses_starttls_login_and_send(self) -> None:
        client = SMTPEmailClient(
            host="smtp.example.com",
            username="me@example.com",
            password="secret",
            from_email="Me <me@example.com>",
            smtp_factory=_factory(),
        )
        result = client.send(
            EmailMessagePayload(
                to_email="them@example.com",
                subject="Hi there",
                body="A friendly message.",
                resident_id="resident_42",
            )
        )

        self.assertEqual(result.status, "sent")
        self.assertEqual(result.provider, "smtp")
        self.assertEqual(len(_FakeSMTP.instances), 1)
        smtp = _FakeSMTP.instances[0]
        self.assertEqual(smtp.host, "smtp.example.com")
        self.assertEqual(smtp.port, 587)
        self.assertTrue(smtp.starttls_called)
        self.assertEqual(smtp.login_args, ("me@example.com", "secret"))
        self.assertEqual(len(smtp.sent_messages), 1)
        sent = smtp.sent_messages[0]
        self.assertEqual(sent["From"], "Me <me@example.com>")
        self.assertEqual(sent["To"], "them@example.com")
        self.assertEqual(sent["Subject"], "Hi there")
        self.assertIn("A friendly message.", sent.get_content())
        self.assertTrue(smtp.quit_called)

    def test_for_gmail_uses_gmail_smtp_defaults(self) -> None:
        client = SMTPEmailClient.for_gmail(
            username="me@gmail.com",
            app_password="abcd efgh ijkl mnop",
            smtp_factory=_factory(),
        )
        result = client.send(
            EmailMessagePayload(
                to_email="friend@example.com",
                subject="Coffee?",
                body="Wanna grab a coffee?",
                resident_id="r1",
            )
        )
        self.assertEqual(result.status, "sent")
        smtp = _FakeSMTP.instances[0]
        self.assertEqual(smtp.host, "smtp.gmail.com")
        self.assertEqual(smtp.port, 587)
        sent = smtp.sent_messages[0]
        self.assertEqual(sent["From"], "me@gmail.com")

    def test_auth_failure_returns_failed_status(self) -> None:
        client = SMTPEmailClient(
            host="smtp.example.com",
            username="me",
            password="bad",
            from_email="me@x.com",
            smtp_factory=_factory(login_should_fail=True),
        )
        result = client.send(
            EmailMessagePayload(
                to_email="t@x.com",
                subject="s",
                body="b",
                resident_id="r1",
            )
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("auth failed", (result.error_message or "").lower())
        self.assertTrue(_FakeSMTP.instances[0].quit_called)

    def test_send_failure_returns_failed_status(self) -> None:
        client = SMTPEmailClient(
            host="smtp.example.com",
            username="me",
            password="p",
            from_email="me@x.com",
            smtp_factory=_factory(send_should_fail=True),
        )
        result = client.send(
            EmailMessagePayload(
                to_email="t@x.com",
                subject="s",
                body="b",
                resident_id="r1",
            )
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("relay refused", result.error_message or "")

    def test_build_email_client_from_env_picks_smtp(self) -> None:
        old = {k: os.environ.pop(k, None) for k in _SMTP_ENV_KEYS}
        try:
            os.environ["SMTP_HOST"] = "smtp.gmail.com"
            os.environ["SMTP_USERNAME"] = "me@gmail.com"
            os.environ["SMTP_PASSWORD"] = "app-password"
            client = build_email_client_from_env()
            self.assertIsInstance(client, SMTPEmailClient)

            os.environ["RESEND_API_KEY"] = "re_x"
            os.environ["EMAIL_FROM"] = "Me <me@gmail.com>"
            client2 = build_email_client_from_env()
            self.assertIsInstance(
                client2,
                SMTPEmailClient,
                "SMTP should take priority over Resend when both are set.",
            )
            os.environ.pop("SMTP_HOST")
            client3 = build_email_client_from_env()
            self.assertIsInstance(client3, ResendEmailClient)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_build_email_client_from_env_warns_on_incomplete_smtp(self) -> None:
        old = {k: os.environ.pop(k, None) for k in _SMTP_ENV_KEYS}
        try:
            os.environ["SMTP_HOST"] = "smtp.gmail.com"
            os.environ["SMTP_USERNAME"] = "me@gmail.com"
            self.assertIsNone(build_email_client_from_env())
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
