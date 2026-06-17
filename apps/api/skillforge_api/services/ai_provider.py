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

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = base_url if base_url is not None else self._settings.openai_base_url
        self._api_key = api_key if api_key is not None else self._settings.openai_api_key
        self._model = model or self._settings.model
        if not self._api_key:
            raise AIProviderError(
                "An API key is required for the openai-compatible provider"
            )

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = self._base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
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

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = base_url if base_url is not None else self._settings.ollama_base_url
        self._model = model or self._settings.model

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = self._base_url.rstrip("/") + "/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
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
    """Return the configured :class:`AIProvider` instance (env-driven, legacy)."""
    settings = settings or get_settings()
    kind = settings.ai_provider
    if kind == "mock":
        return MockProvider()
    if kind == "openai-compatible":
        return OpenAICompatibleProvider(settings)
    if kind == "ollama-local":
        return OllamaProvider(settings)
    raise AIProviderError(f"Unknown AI provider: {kind!r}")


def get_provider_for_config(cfg) -> AIProvider:
    """Build a provider from a :class:`ProviderConfig` (user/UI config).

    This is the runtime path used by the planner and the chat router: it honors
    the user's UI-configured provider/model/key, falling back to env defaults
    only when a field is empty (handled by ``ProviderConfig.merged_over``).
    """
    # Local import avoids a cycle (user_config imports settings).
    from .user_config import ProviderConfig

    if not isinstance(cfg, ProviderConfig):
        raise AIProviderError("get_provider_for_config expects a ProviderConfig")

    kind = (cfg.provider or "mock").strip()
    if kind == "mock":
        return MockProvider()
    if kind == "openai-compatible":
        if not cfg.openai_api_key:
            raise AIProviderError(
                "An API key is required for the openai-compatible provider. "
                "Set it in Settings."
            )
        return OpenAICompatibleProvider(
            base_url=cfg.openai_base_url, api_key=cfg.openai_api_key, model=cfg.model
        )
    if kind == "ollama-local":
        return OllamaProvider(base_url=cfg.ollama_base_url, model=cfg.model)
    raise AIProviderError(f"Unknown AI provider: {kind!r}")


def get_active_provider() -> AIProvider:
    """Return the provider honoring the current user config (file > env > default)."""
    from .user_config import get_user_config_store

    cfg = get_user_config_store().get_provider()
    try:
        return get_provider_for_config(cfg)
    except AIProviderError:
        # If the user's config is incomplete (e.g. no key yet), fall back to the
        # env-driven provider so the app stays usable (mock by default).
        return get_provider()


# ----------------------------------------------------------------------------
# Connection testing + model enumeration (S2)
# ----------------------------------------------------------------------------


def test_provider_connection(cfg) -> dict[str, Any]:
    """Lightweight liveness probe for a provider config.

    Returns ``{"ok": bool, "detail": str}``. Never raises — callers (the UI)
    want a structured result, not an exception.

    For OpenAI-compatible providers we try ``/models`` first; if that endpoint
    is missing we fall back to a 1-token ``/chat/completions`` probe (the only
    endpoint SkillForge actually needs). Auth errors surface a clear message so
    users know to fix the key rather than the URL.
    """
    from .user_config import ProviderConfig

    kind = (cfg.provider or "mock").strip()
    if kind == "mock":
        return {"ok": True, "detail": "mock provider is always available"}
    if kind == "openai-compatible":
        if not cfg.openai_api_key:
            return {"ok": False, "detail": "No API key set"}
        base = cfg.openai_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {cfg.openai_api_key}"}
        # 1) Try /models (cheap, lists models). Many providers implement it.
        try:
            resp = httpx.get(f"{base}/models", headers=headers, timeout=10.0)
            if resp.status_code == 401:
                return {"ok": False, "detail": "Auth failed (401) — check the API key."}
            if resp.status_code == 404:
                # /models not implemented; fall through to chat probe.
                pass
            elif 200 <= resp.status_code < 300:
                return {"ok": True, "detail": f"connected (HTTP {resp.status_code})"}
            else:
                # Other non-2xx on /models → try chat before declaring failure.
                pass
        except httpx.HTTPError as exc:
            # Network error on /models → try chat (different path) before failing.
            pass
        # 2) Fall back to a minimal chat completion — the real workload path.
        try:
            resp = httpx.post(
                f"{base}/chat/completions",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": cfg.model or "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
                timeout=15.0,
            )
            if resp.status_code == 401:
                return {"ok": False, "detail": "Auth failed (401) — check the API key."}
            if 200 <= resp.status_code < 300:
                return {"ok": True, "detail": f"connected (chat HTTP {resp.status_code})"}
            return {
                "ok": False,
                "detail": f"chat endpoint returned HTTP {resp.status_code}: {resp.text[:160]}",
            }
        except httpx.HTTPError as exc:
            return {"ok": False, "detail": f"connection failed: {exc}"}
    if kind == "ollama-local":
        try:
            resp = httpx.get(cfg.ollama_base_url.rstrip("/") + "/api/tags", timeout=10.0)
            if 200 <= resp.status_code < 300:
                return {"ok": True, "detail": f"connected (HTTP {resp.status_code})"}
            return {"ok": False, "detail": f"/api/tags returned HTTP {resp.status_code}"}
        except httpx.HTTPError as exc:
            return {"ok": False, "detail": f"connection failed: {exc}"}
    return {"ok": False, "detail": f"unknown provider: {kind}"}


def list_models(cfg) -> list[str]:
    """Return available model names for a provider config (best-effort)."""
    from .user_config import ProviderConfig

    kind = (cfg.provider or "mock").strip()
    if kind == "mock":
        return ["mock-model"]
    if kind == "openai-compatible":
        if not cfg.openai_api_key:
            return []
        try:
            url = cfg.openai_base_url.rstrip("/") + "/models"
            resp = httpx.get(
                url,
                headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("id") or m.get("name") for m in data.get("data", [])]
            return [m for m in models if m]
        except httpx.HTTPError:
            return []
    if kind == "ollama-local":
        try:
            resp = httpx.get(cfg.ollama_base_url.rstrip("/") + "/api/tags", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except httpx.HTTPError:
            return []
    return []


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
