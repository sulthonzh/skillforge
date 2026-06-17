"""AI provider abstraction.

SkillForge talks to LLMs through a single :class:`AIProvider` interface. Three
implementations ship in the box:

* :class:`MockProvider`        — deterministic, offline, for tests and zero-config runs.
* :class:`OpenAICompatibleProvider` — works with OpenAI, OpenRouter, Together, Groq, vLLM, ...
* :class:`OllamaProvider`      — local LLMs served by Ollama.

Both network providers use a strict JSON contract and parse defensively. The
mock provider can be forced at any time via ``SKILLFORGE_AI_PROVIDER=mock``.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..settings import Settings, get_settings

log = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """Raised when an AI provider call fails."""


class AIProvider(ABC):
    """Minimal chat-completion provider returning raw assistant text."""

    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        """Return the assistant's raw text response.

        When ``json_mode`` is True, callers expect a JSON-parseable string.
        """

    # Convenience helper for JSON-returning prompts.
    def complete_json(self, system: str, user: str) -> Any:
        raw = self.complete(system, user, json_mode=True)
        return _coerce_json(raw)


# ----------------------------------------------------------------------------
# Mock provider
# ----------------------------------------------------------------------------


class MockProvider(AIProvider):
    """Deterministic offline provider.

    Useful for tests, CI, and first runs without an API key. It does no real
    reasoning — it simply returns a well-formed manifest scaffold based on
    keyword heuristics, so the rest of the pipeline can run end-to-end.
    """

    name = "mock"

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        # The planner builds its own mock manifest directly; this hook exists so
        # any future "pure chat" call still returns something sensible.
        if json_mode:
            return json.dumps({"reply": user, "mock": True})
        return f"[mock] I understood: {user}"


# ----------------------------------------------------------------------------
# OpenAI-compatible provider
# ----------------------------------------------------------------------------


class OpenAICompatibleProvider(AIProvider):
    """Works against any OpenAI-compatible ``/chat/completions`` endpoint."""

    name = "openai-compatible"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise AIProviderError(
                "SKILLFORGE_OPENAI_API_KEY is required for the openai-compatible provider"
            )

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = self._settings.openai_base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"OpenAI-compatible request failed: {exc}") from exc

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected provider response shape: {data!r}") from exc


# ----------------------------------------------------------------------------
# Ollama provider
# ----------------------------------------------------------------------------


class OllamaProvider(AIProvider):
    """Talks to a local Ollama daemon (``/api/chat``)."""

    name = "ollama-local"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = self._settings.ollama_base_url.rstrip("/") + "/api/chat"
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "stream": False,
            "format": "json" if json_mode else None,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.2},
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            resp = httpx.post(url, json=payload, timeout=120.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc

        data = resp.json()
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Ollama response shape: {data!r}") from exc


# ----------------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------------


def get_provider(settings: Settings | None = None) -> AIProvider:
    """Return the configured :class:`AIProvider` instance."""
    settings = settings or get_settings()
    kind = settings.ai_provider
    if kind == "mock":
        return MockProvider()
    if kind == "openai-compatible":
        return OpenAICompatibleProvider(settings)
    if kind == "ollama-local":
        return OllamaProvider(settings)
    raise AIProviderError(f"Unknown AI provider: {kind!r}")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _coerce_json(raw: str) -> Any:
    """Parse JSON from a model response, tolerating code fences and prose."""
    if raw is None:
        raise AIProviderError("Empty AI response")
    text = raw.strip()

    # Strip a leading ```json fence if present.
    if text.startswith("```"):
        m = _JSON_FENCE_RE.search(text)
        if m:
            text = m.group(1).strip()

    # If there's still surrounding prose, try to slice the outermost object/array.
    if not (text.startswith("{") or text.startswith("[")):
        start = min(
            (i for i in (text.find("{"), text.find("[")) if i >= 0),
            default=-1,
        )
        if start >= 0:
            text = text[start:]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"AI response was not valid JSON: {exc}\n--- raw ---\n{raw}") from exc
