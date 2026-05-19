"""LLM client interface used by the activity-planning service.

The interface is intentionally narrow: callers pass a prompt and a JSON
schema, the client returns a parsed dict (or raises). The shape lets the
service layer stay agnostic of the underlying provider and lets tests
inject a deterministic fake without depending on the `openai` package or
the network.

Production: :class:`OpenAIChatLLMClient` wraps the official `openai`
Python SDK. The dependency is intentionally optional: importing this
module never requires `openai` to be installed. The client is constructed
lazily so missing API key / package only raises when the operator
actually requests a generation. By default it uses OpenAI's Responses API
with web search enabled, because activity planning is expected to research
real Rotterdam venues.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


logger = logging.getLogger(__name__)


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_OUTPUT_TOKENS = 1500


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM client cannot be configured (missing key/package)."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM response cannot be parsed as the required JSON."""


@dataclass(slots=True, frozen=True)
class LLMResponse:
    """Parsed structured response from an LLM call."""

    content: dict[str, Any]
    raw_text: str
    model_provider: str
    model_name: str


class LLMClient(Protocol):
    """Minimal interface every LLM backend must implement."""

    @property
    def model_provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate_json(
        self,
        *,
        prompt: str,
        json_schema: Mapping[str, Any],
        system_prompt: str | None = None,
    ) -> LLMResponse: ...


class OpenAIChatLLMClient:
    """Production LLM client backed by the official OpenAI Python SDK.

    The constructor only stores configuration. The OpenAI client itself is
    created on first use so importing this module does not require the
    `openai` package to be installed.
    """

    model_provider = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str = DEFAULT_OPENAI_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        enable_web_search: bool = True,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model_name = model_name
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._enable_web_search = enable_web_search
        self._client: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not configured. "
                "Set the environment variable or pass api_key=... to "
                "OpenAIChatLLMClient."
            )
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised only without dep
            raise LLMConfigurationError(
                "openai Python package is not installed. "
                "Install it (e.g. `pip install openai`) to enable the "
                "activity-planning service."
            ) from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def generate_json(
        self,
        *,
        prompt: str,
        json_schema: Mapping[str, Any],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.info(
            "llm.openai.request model=%s temperature=%.2f web_search=%s",
            self._model_name,
            self._temperature,
            self._enable_web_search,
        )
        if self._enable_web_search:
            return self._generate_json_with_responses_api(
                client=client,
                prompt=prompt,
                json_schema=json_schema,
                system_prompt=system_prompt,
            )

        completion = client.chat.completions.create(
            model=self._model_name,
            temperature=self._temperature,
            max_tokens=self._max_output_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "activity_plan",
                    "schema": dict(json_schema),
                    "strict": True,
                },
            },
            messages=messages,
        )
        raw_text = completion.choices[0].message.content or ""
        try:
            content = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"OpenAI returned non-JSON content: {raw_text[:200]!r}"
            ) from exc
        if not isinstance(content, dict):
            raise LLMResponseError(
                f"OpenAI returned non-object JSON: {type(content).__name__}"
            )
        return LLMResponse(
            content=content,
            raw_text=raw_text,
            model_provider=self.model_provider,
            model_name=self._model_name,
        )

    def _generate_json_with_responses_api(
        self,
        *,
        client: Any,
        prompt: str,
        json_schema: Mapping[str, Any],
        system_prompt: str | None,
    ) -> LLMResponse:
        input_items: list[dict[str, str]] = []
        if system_prompt:
            input_items.append({"role": "system", "content": system_prompt})
        input_items.append({"role": "user", "content": prompt})
        try:
            response = client.responses.create(
                model=self._model_name,
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
                tools=[{"type": "web_search_preview"}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "activity_plan",
                        "schema": dict(json_schema),
                        "strict": True,
                    }
                },
                input=input_items,
            )
        except TypeError as exc:
            raise LLMConfigurationError(
                "Installed openai package does not support Responses API web "
                "search parameters. Upgrade `openai` or construct "
                "OpenAIChatLLMClient(enable_web_search=False)."
            ) from exc

        raw_text = getattr(response, "output_text", "") or ""
        if not raw_text:
            raw_text = _extract_response_text(response)
        try:
            content = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"OpenAI returned non-JSON content: {raw_text[:200]!r}"
            ) from exc
        if not isinstance(content, dict):
            raise LLMResponseError(
                f"OpenAI returned non-object JSON: {type(content).__name__}"
            )
        return LLMResponse(
            content=content,
            raw_text=raw_text,
            model_provider=self.model_provider,
            model_name=self._model_name,
        )


def _extract_response_text(response: Any) -> str:
    """Best-effort text extraction for SDK response objects."""
    output = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output:
        content_items = getattr(item, "content", None) or []
        for content in content_items:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


__all__ = [
    "DEFAULT_OPENAI_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "LLMClient",
    "LLMConfigurationError",
    "LLMResponse",
    "LLMResponseError",
    "OpenAIChatLLMClient",
]
