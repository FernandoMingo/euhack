"""Email delivery interface used by the invitation inbox service.

The default implementation (`QueuedEmailClient`) never sends a real
email; it simply reports that the message is queued so the service
persists it with `delivery_status='queued'`. Real provider integrations
or tests can swap in a different `EmailClient`.

Two real implementations ship in this module:

* `SMTPEmailClient` — sends via plain SMTP (stdlib ``smtplib``). The
  preferred path when you do not own a domain: with a Gmail address and
  an App Password you can use ``smtp.gmail.com:587`` and Gmail will
  appear as the From address.
* `ResendEmailClient` — sends via the Resend HTTP API. Requires a
  verified domain in production but no extra Python dependency beyond
  ``httpx`` (already required by FastAPI).

`build_email_client_from_env()` chooses one of them based on env vars:

* ``SMTP_HOST`` set (plus ``SMTP_USERNAME`` / ``SMTP_PASSWORD`` /
  ``EMAIL_FROM``) -> ``SMTPEmailClient``.
* ``RESEND_API_KEY`` and ``EMAIL_FROM`` set -> ``ResendEmailClient``.
* otherwise returns ``None`` so callers keep using ``QueuedEmailClient``.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Protocol


logger = logging.getLogger(__name__)


class EmailConfigurationError(RuntimeError):
    """Raised when a real email client is constructed with invalid settings."""


@dataclass(slots=True, frozen=True)
class EmailMessagePayload:
    """The exact content that an `EmailClient` will be asked to deliver.

    ``body`` is the canonical plain-text version persisted on the
    ``outbound_email_messages`` row. ``html_body``, when present, is
    attached as a ``multipart/alternative`` HTML part so well-behaved
    clients render the styled version while plain-text-only clients
    still receive readable copy.
    """

    to_email: str
    subject: str
    body: str
    resident_id: str
    html_body: str | None = None


@dataclass(slots=True, frozen=True)
class EmailDeliveryResult:
    """Result returned by an `EmailClient.send`.

    `status` is the new `delivery_status` for the outbound row:
    `queued` (no attempt was made), `sent` (provider accepted),
    `failed` (provider errored), or `skipped` (intentional no-op,
    e.g. for tests).
    """

    status: str
    provider: str
    provider_message_id: str | None = None
    error_message: str | None = None


class EmailClient(Protocol):
    """Narrow interface for outbound email delivery.

    Implementations should be cheap to construct and free of side
    effects until `send` is called. They must not perform any database
    writes; persistence is owned by the service layer.
    """

    provider_name: str

    def send(self, message: EmailMessagePayload) -> EmailDeliveryResult: ...


class QueuedEmailClient:
    """Default no-send client.

    Marks every message as `queued` so the row sits in the outbound
    queue until an operator (or a different client) decides to deliver
    it. This is what runs by default so `send_invitations_for_approved_circle`
    never dispatches a real email without explicit opt-in.
    """

    provider_name: str = "queued"

    def send(self, message: EmailMessagePayload) -> EmailDeliveryResult:
        return EmailDeliveryResult(status="queued", provider=self.provider_name)


class FakeEmailClient:
    """Test double that records sends and returns a configurable result.

    Tests can assert on `sent_messages` to verify the inbox service
    only attempts the deliveries it should. The default behaviour is
    `status='queued'` so tests confirm no real send occurs unless
    explicitly opted in.
    """

    provider_name: str = "fake"

    def __init__(
        self,
        *,
        default_status: str = "queued",
        provider_name: str = "fake",
        provider_message_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self._default_status = default_status
        self._provider_message_id = provider_message_id
        self._error_message = error_message
        self.sent_messages: list[EmailMessagePayload] = []

    def send(self, message: EmailMessagePayload) -> EmailDeliveryResult:
        self.sent_messages.append(message)
        return EmailDeliveryResult(
            status=self._default_status,
            provider=self.provider_name,
            provider_message_id=self._provider_message_id,
            error_message=self._error_message,
        )


class ResendEmailClient:
    """Send transactional email through Resend's REST API.

    The client is synchronous and stateless aside from optional HTTP client
    injection for tests. Successful API responses return
    ``EmailDeliveryResult(status='sent', provider_message_id=...)``.
    HTTP errors return ``status='failed'`` with ``error_message`` set;
    the invitation inbox service persists that on the outbound row.
    """

    provider_name: str = "resend"

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        base_url: str = "https://api.resend.com",
        timeout: float = 30.0,
        http_client: Any = None,
    ) -> None:
        import httpx as _httpx  # local import keeps module import light

        key = api_key.strip()
        sender = from_email.strip()
        if not key:
            raise EmailConfigurationError("ResendEmailClient requires a non-empty api_key")
        if not sender:
            raise EmailConfigurationError("ResendEmailClient requires a non-empty from_email")
        self._api_key = key
        self._from_email = sender
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http_client = http_client
        self._httpx = _httpx

    def send(self, message: EmailMessagePayload) -> EmailDeliveryResult:
        url = f"{self._base_url}/emails"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "from": self._from_email,
            "to": [message.to_email],
            "subject": message.subject,
            "text": message.body,
        }
        if message.html_body:
            payload["html"] = message.html_body
        try:
            if self._http_client is not None:
                response = self._http_client.post(url, headers=headers, json=payload)
            else:
                response = self._httpx.post(
                    url, headers=headers, json=payload, timeout=self._timeout
                )
        except self._httpx.RequestError as exc:
            return EmailDeliveryResult(
                status="failed",
                provider=self.provider_name,
                error_message=f"Resend request failed: {exc}",
            )

        if response.status_code >= 200 and response.status_code < 300:
            provider_id: str | None = None
            try:
                data = response.json()
                if isinstance(data, dict):
                    raw = data.get("id")
                    provider_id = str(raw) if raw is not None else None
            except json.JSONDecodeError:
                provider_id = None
            return EmailDeliveryResult(
                status="sent",
                provider=self.provider_name,
                provider_message_id=provider_id,
            )

        err = _resend_error_text(response)
        return EmailDeliveryResult(
            status="failed",
            provider=self.provider_name,
            error_message=err,
        )


def _resend_error_text(response: object) -> str:
    """Best-effort extract Resend error message from an HTTP response."""
    code = getattr(response, "status_code", "?")
    try:
        json_method = getattr(response, "json", None)
        if callable(json_method):
            parsed = json_method()
            if isinstance(parsed, dict):
                msg = parsed.get("message")
                if isinstance(msg, str) and msg:
                    return f"Resend HTTP {code}: {msg}"
    except Exception:
        pass
    body = (getattr(response, "text", None) or "").strip()
    if body:
        return f"Resend HTTP {code}: {body[:500]}"
    return f"Resend HTTP {code}"


class SMTPEmailClient:
    """Send transactional email through a plain SMTP server (stdlib).

    Designed to work with Gmail SMTP out of the box but accepts any
    standard SMTP host. With Gmail you do **not** need a custom domain:
    use your Gmail address as both the username and the From address
    (Gmail rewrites it to your real account on send).

    Authentication notes:
    - Gmail blocks the regular account password for third-party apps.
      Enable 2-Step Verification, then create an **App Password** at
      https://myaccount.google.com/apppasswords and use that as
      ``password``.
    - ``use_ssl=True`` uses an implicit-TLS port (default 465).
      ``use_starttls=True`` (the default) upgrades a plaintext
      connection on port 587 — this is the Gmail-recommended setup.
    """

    provider_name: str = "smtp"

    def __init__(
        self,
        *,
        host: str,
        username: str,
        password: str,
        from_email: str,
        port: int | None = None,
        use_starttls: bool = True,
        use_ssl: bool = False,
        timeout: float = 30.0,
        smtp_factory: Any = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        host_clean = (host or "").strip()
        user_clean = (username or "").strip()
        from_clean = (from_email or "").strip()
        if not host_clean:
            raise EmailConfigurationError("SMTPEmailClient requires a non-empty host")
        if not user_clean:
            raise EmailConfigurationError(
                "SMTPEmailClient requires a non-empty username"
            )
        if not password:
            raise EmailConfigurationError(
                "SMTPEmailClient requires a non-empty password"
            )
        if not from_clean:
            raise EmailConfigurationError(
                "SMTPEmailClient requires a non-empty from_email"
            )
        if use_ssl and use_starttls:
            raise EmailConfigurationError(
                "SMTPEmailClient: choose either use_ssl or use_starttls, not both"
            )
        self._host = host_clean
        self._username = user_clean
        self._password = password
        self._from_email = from_clean
        self._port = port if port is not None else (465 if use_ssl else 587)
        self._use_starttls = use_starttls and not use_ssl
        self._use_ssl = use_ssl
        self._timeout = timeout
        self._ssl_context = ssl_context
        # smtp_factory lets tests inject a fake constructor returning a
        # context-manager-compatible object exposing ehlo / starttls /
        # login / send_message.
        self._smtp_factory = smtp_factory

    @classmethod
    def for_gmail(
        cls,
        *,
        username: str,
        app_password: str,
        from_email: str | None = None,
        **kwargs: Any,
    ) -> "SMTPEmailClient":
        """Convenience constructor for Gmail SMTP via App Password."""
        return cls(
            host="smtp.gmail.com",
            port=587,
            use_starttls=True,
            username=username,
            password=app_password,
            from_email=from_email or username,
            **kwargs,
        )

    def send(self, message: EmailMessagePayload) -> EmailDeliveryResult:
        mime = EmailMessage()
        mime["From"] = self._from_email
        mime["To"] = message.to_email
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        if message.html_body:
            mime.add_alternative(message.html_body, subtype="html")

        try:
            smtp = self._open_smtp()
        except (smtplib.SMTPException, OSError) as exc:
            return EmailDeliveryResult(
                status="failed",
                provider=self.provider_name,
                error_message=f"SMTP connect failed: {exc}",
            )

        try:
            try:
                if self._use_starttls:
                    smtp.ehlo()
                    context = self._ssl_context or ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                smtp.login(self._username, self._password)
                smtp.send_message(mime)
            except smtplib.SMTPAuthenticationError as exc:
                return EmailDeliveryResult(
                    status="failed",
                    provider=self.provider_name,
                    error_message=(
                        f"SMTP auth failed ({exc.smtp_code}): "
                        f"{_decode_smtp_bytes(exc.smtp_error)}"
                    ),
                )
            except smtplib.SMTPException as exc:
                return EmailDeliveryResult(
                    status="failed",
                    provider=self.provider_name,
                    error_message=f"SMTP send failed: {exc}",
                )
        finally:
            try:
                smtp.quit()
            except smtplib.SMTPException:
                pass

        msg_id = mime.get("Message-ID")
        return EmailDeliveryResult(
            status="sent",
            provider=self.provider_name,
            provider_message_id=msg_id,
        )

    def _open_smtp(self) -> Any:
        if self._smtp_factory is not None:
            return self._smtp_factory(self._host, self._port)
        if self._use_ssl:
            context = self._ssl_context or ssl.create_default_context()
            return smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout, context=context
            )
        return smtplib.SMTP(self._host, self._port, timeout=self._timeout)


def _decode_smtp_bytes(value: object) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return repr(value)
    return str(value)


def build_email_client_from_env() -> EmailClient | None:
    """Pick an email client based on the current process environment.

    Priority:

    1. ``SMTP_HOST`` + ``SMTP_USERNAME`` + ``SMTP_PASSWORD`` (+ ``EMAIL_FROM``
       fallback to the username) -> ``SMTPEmailClient`` (works with Gmail
       SMTP and any other SMTP provider).
    2. ``RESEND_API_KEY`` + ``EMAIL_FROM`` -> ``ResendEmailClient``.
    3. otherwise ``None`` so the queued no-op path is used.

    Partial/invalid configuration logs a warning and falls back instead
    of crashing startup.
    """
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    if smtp_host:
        username = os.environ.get("SMTP_USERNAME", "").strip()
        password = os.environ.get("SMTP_PASSWORD", "")
        from_addr = (
            os.environ.get("EMAIL_FROM", "").strip()
            or username
        )
        port_raw = os.environ.get("SMTP_PORT", "").strip()
        use_ssl_raw = os.environ.get("SMTP_USE_SSL", "").strip().lower()
        use_starttls_raw = os.environ.get("SMTP_USE_STARTTLS", "").strip().lower()
        use_ssl = use_ssl_raw in {"1", "true", "yes", "on"}
        # default to STARTTLS unless SMTP_USE_SSL is explicitly true
        use_starttls = (
            use_starttls_raw in {"", "1", "true", "yes", "on"}
            and not use_ssl
        )
        port: int | None = None
        if port_raw:
            try:
                port = int(port_raw)
            except ValueError:
                logger.warning(
                    "SMTP_PORT=%r is not an integer; ignoring and using default port.",
                    port_raw,
                )
                port = None
        if not username or not password or not from_addr:
            logger.warning(
                "SMTP_HOST is set but SMTP_USERNAME/SMTP_PASSWORD/EMAIL_FROM "
                "are incomplete; invitation emails remain queued."
            )
            return None
        try:
            return SMTPEmailClient(
                host=smtp_host,
                username=username,
                password=password,
                from_email=from_addr,
                port=port,
                use_ssl=use_ssl,
                use_starttls=use_starttls,
            )
        except EmailConfigurationError as exc:
            logger.warning("SMTP email client rejected env config: %s", exc)
            return None

    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        return None
    from_addr = os.environ.get("EMAIL_FROM", "").strip()
    if not from_addr:
        logger.warning(
            "RESEND_API_KEY is set but EMAIL_FROM is empty; "
            "invitation emails remain queued until EMAIL_FROM is configured."
        )
        return None
    return ResendEmailClient(api_key=key, from_email=from_addr)


__all__ = [
    "EmailClient",
    "EmailConfigurationError",
    "EmailDeliveryResult",
    "EmailMessagePayload",
    "FakeEmailClient",
    "QueuedEmailClient",
    "ResendEmailClient",
    "SMTPEmailClient",
    "build_email_client_from_env",
]
