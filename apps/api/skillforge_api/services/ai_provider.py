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
# Anthropic provider (native Messages API)
# ----------------------------------------------------------------------------


class AnthropicProvider(AIProvider):
    """Talks to Anthropic's native Messages API (``/v1/messages``).

    Anthropic differs from OpenAI in three ways that matter to us:
      * auth is ``x-api-key`` (plus an ``anthropic-version`` header), not Bearer;
      * the system prompt is a *top-level* field, not a message role;
      * the response payload nests content under ``content[0].text``.

    Supports JSON output by instructing the model to return JSON (Anthropic has
    no native ``response_format``), then coerced via the shared ``_coerce_json``.
    """

    name = "anthropic"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: Any = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = base_url if base_url is not None else "https://api.anthropic.com"
        self._api_key = api_key if api_key is not None else getattr(self._settings, "anthropic_api_key", "")
        self._model = model or getattr(self._settings, "model", "") or "claude-3-5-sonnet-latest"
        # Optional transport for tests (httpx.MockTransport). Production uses None
        # → a fresh httpx.Client per call (module-level httpx.post).
        self._transport = transport
        if not self._api_key:
            raise AIProviderError(
                "An API key is required for the anthropic provider"
            )

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = self._base_url.rstrip("/") + "/v1/messages"
        # Anthropic has no native JSON mode; append a JSON-only instruction.
        sys_content = system
        user_content = user
        if json_mode:
            user_content = user + "\n\nReturn ONLY a JSON object. No prose, no code fences."
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 2048,
            "temperature": 0.2,
            "system": sys_content,
            "messages": [{"role": "user", "content": user_content}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        try:
            if self._transport is not None:
                with httpx.Client(transport=self._transport) as client:
                    resp = client.post(url, json=payload, headers=headers, timeout=60.0)
            else:
                resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Anthropic request failed: {exc}") from exc

        data = resp.json()
        # Response shape: {"content": [{"type": "text", "text": "..."}], ...}
        try:
            content = data["content"]
            if isinstance(content, list) and content:
                # Prefer the first text block.
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return str(block.get("text", ""))
                # Fall back to the first block's text field.
                return str(content[0].get("text", ""))
            raise AIProviderError(f"Anthropic response had no text content: {data!r}")
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Anthropic response shape: {data!r}") from exc


# ----------------------------------------------------------------------------
# Google Gemini provider (Generative Language API)
# ----------------------------------------------------------------------------


class GeminiProvider(AIProvider):
    """Talks to Google's Generative Language API (``generateContent``).

    Gemini differs from OpenAI in three ways that matter:
      * auth via ``x-goog-api-key`` header (or ``?key=`` query);
      * requests nest messages as ``contents`` with ``parts``, and the system
        instruction is a separate ``systemInstruction`` field;
      * the response nests text under ``candidates[0].content.parts[0].text``.

    Model is part of the URL path, not the body.
    """

    name = "gemini"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: Any = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = base_url if base_url is not None else getattr(
            self._settings, "gemini_base_url", "https://generativelanguage.googleapis.com"
        )
        self._api_key = api_key if api_key is not None else getattr(self._settings, "gemini_api_key", "")
        self._model = model or getattr(self._settings, "model", "") or "gemini-1.5-flash"
        self._transport = transport
        if not self._api_key:
            raise AIProviderError("An API key is required for the gemini provider")

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = (
            f"{self._base_url.rstrip('/')}/v1beta/models/{self._model}:generateContent"
        )
        user_content = user
        if json_mode:
            user_content = user + "\n\nReturn ONLY a JSON object. No prose, no code fences."
        body: dict[str, Any] = {
            "systemInstruction": {"parts": {"text": system}} if system else None,
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
            if json_mode
            else {"temperature": 0.2},
        }
        body = {k: v for k, v in body.items() if v is not None}
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        try:
            if self._transport is not None:
                with httpx.Client(transport=self._transport) as client:
                    resp = client.post(url, json=body, headers=headers, timeout=60.0)
            else:
                resp = httpx.post(url, json=body, headers=headers, timeout=60.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Gemini request failed: {exc}") from exc

        data = resp.json()
        try:
            return str(data["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Gemini response shape: {data!r}") from exc


# ----------------------------------------------------------------------------
# Cohere provider (Command R+ Chat API)
# ----------------------------------------------------------------------------


class CohereProvider(AIProvider):
    """Talks to Cohere's Chat API (``/v1/chat``).

    Cohere uses a Bearer token but its own message shape: a top-level ``message``
    string + optional ``preamble`` (system). The response nests text under
    ``text`` (top level) for non-stream chat.
    """

    name = "cohere"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        transport: Any = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = base_url if base_url is not None else getattr(
            self._settings, "cohere_base_url", "https://api.cohere.com"
        )
        self._api_key = api_key if api_key is not None else getattr(self._settings, "cohere_api_key", "")
        self._model = model or getattr(self._settings, "model", "") or "command-r-plus"
        self._transport = transport
        if not self._api_key:
            raise AIProviderError("An API key is required for the cohere provider")

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        url = self._base_url.rstrip("/") + "/v1/chat"
        message = user
        if json_mode:
            message = user + "\n\nReturn ONLY a JSON object. No prose, no code fences."
        body: dict[str, Any] = {
            "model": self._model,
            "message": message,
            "temperature": 0.2,
        }
        if system:
            body["preamble"] = system
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            if self._transport is not None:
                with httpx.Client(transport=self._transport) as client:
                    resp = client.post(url, json=body, headers=headers, timeout=60.0)
            else:
                resp = httpx.post(url, json=body, headers=headers, timeout=60.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Cohere request failed: {exc}") from exc

        data = resp.json()
        # Non-stream chat returns {"text": "...", ...}.
        if isinstance(data.get("text"), str):
            return data["text"]
        # Some responses nest under message.content[0].text.
        try:
            return str(data["message"]["content"][0]["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Cohere response shape: {data!r}") from exc


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
    if kind == "anthropic":
        return AnthropicProvider(settings)
    if kind == "gemini":
        return GeminiProvider(settings)
    if kind == "cohere":
        return CohereProvider(settings)
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
    if kind == "anthropic":
        if not cfg.anthropic_api_key:
            raise AIProviderError(
                "An API key is required for the anthropic provider. Set it in Settings."
            )
        return AnthropicProvider(
            base_url=cfg.anthropic_base_url, api_key=cfg.anthropic_api_key, model=cfg.model
        )
    if kind == "gemini":
        if not cfg.gemini_api_key:
            raise AIProviderError(
                "An API key is required for the gemini provider. Set it in Settings."
            )
        return GeminiProvider(
            base_url=cfg.gemini_base_url, api_key=cfg.gemini_api_key, model=cfg.model
        )
    if kind == "cohere":
        if not cfg.cohere_api_key:
            raise AIProviderError(
                "An API key is required for the cohere provider. Set it in Settings."
            )
        return CohereProvider(
            base_url=cfg.cohere_base_url, api_key=cfg.cohere_api_key, model=cfg.model
        )
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
    if kind == "anthropic":
        if not cfg.anthropic_api_key:
            return {"ok": False, "detail": "No API key set"}
        base = cfg.anthropic_base_url.rstrip("/")
        # Anthropic exposes /v1/models (list) and /v1/messages (workload). Probe
        # /v1/messages with a 1-token request — the path SkillForge actually uses.
        try:
            resp = httpx.post(
                f"{base}/v1/messages",
                headers={
                    "x-api-key": cfg.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg.model or "claude-3-5-haiku-latest",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
                timeout=15.0,
            )
            if resp.status_code == 401:
                return {"ok": False, "detail": "Auth failed (401) — check the API key."}
            if 200 <= resp.status_code < 300:
                return {"ok": True, "detail": f"connected (HTTP {resp.status_code})"}
            return {
                "ok": False,
                "detail": f"/v1/messages returned HTTP {resp.status_code}: {resp.text[:160]}",
            }
        except httpx.HTTPError as exc:
            return {"ok": False, "detail": f"connection failed: {exc}"}
    if kind == "gemini":
        if not cfg.gemini_api_key:
            return {"ok": False, "detail": "No API key set"}
        base = cfg.gemini_base_url.rstrip("/")
        model = cfg.model or "gemini-1.5-flash"
        # Probe generateContent with a 1-token request.
        try:
            resp = httpx.post(
                f"{base}/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": cfg.gemini_api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": "ping"}]}],
                    "generationConfig": {"maxOutputTokens": 1},
                },
                timeout=15.0,
            )
            if resp.status_code in (400, 401, 403):
                return {"ok": False, "detail": f"Auth/request failed ({resp.status_code}) — check the API key and model."}
            if 200 <= resp.status_code < 300:
                return {"ok": True, "detail": f"connected (HTTP {resp.status_code})"}
            return {"ok": False, "detail": f"generateContent returned HTTP {resp.status_code}: {resp.text[:160]}"}
        except httpx.HTTPError as exc:
            return {"ok": False, "detail": f"connection failed: {exc}"}
    if kind == "cohere":
        if not cfg.cohere_api_key:
            return {"ok": False, "detail": "No API key set"}
        base = cfg.cohere_base_url.rstrip("/")
        try:
            resp = httpx.post(
                f"{base}/v1/chat",
                headers={
                    "Authorization": f"Bearer {cfg.cohere_api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"model": cfg.model or "command-r-plus", "message": "ping", "max_tokens": 1},
                timeout=15.0,
            )
            if resp.status_code in (401, 403):
                return {"ok": False, "detail": f"Auth failed ({resp.status_code}) — check the API key."}
            if 200 <= resp.status_code < 300:
                return {"ok": True, "detail": f"connected (HTTP {resp.status_code})"}
            return {"ok": False, "detail": f"/v1/chat returned HTTP {resp.status_code}: {resp.text[:160]}"}
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
    if kind == "anthropic":
        # Anthropic's /v1/models requires a beta header and returns a fixed list;
        # fall back to well-known model names if the endpoint is unavailable.
        if not cfg.anthropic_api_key:
            return _ANTHROPIC_FALLBACK_MODELS
        try:
            resp = httpx.get(
                cfg.anthropic_base_url.rstrip("/") + "/v1/models",
                headers={
                    "x-api-key": cfg.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10.0,
            )
            if 200 <= resp.status_code < 300:
                data = resp.json()
                names = [m.get("id") for m in data.get("data", []) if m.get("id")]
                return names or _ANTHROPIC_FALLBACK_MODELS
            return _ANTHROPIC_FALLBACK_MODELS
        except httpx.HTTPError:
            return _ANTHROPIC_FALLBACK_MODELS
    if kind == "gemini":
        if not cfg.gemini_api_key:
            return _GEMINI_FALLBACK_MODELS
        try:
            resp = httpx.get(
                cfg.gemini_base_url.rstrip("/") + "/v1beta/models",
                headers={"x-goog-api-key": cfg.gemini_api_key},
                timeout=10.0,
            )
            if 200 <= resp.status_code < 300:
                data = resp.json()
                names = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
                return [n for n in names if n and "generateContent" in str(data)] or _GEMINI_FALLBACK_MODELS
            return _GEMINI_FALLBACK_MODELS
        except httpx.HTTPError:
            return _GEMINI_FALLBACK_MODELS
    if kind == "cohere":
        if not cfg.cohere_api_key:
            return _COHERE_FALLBACK_MODELS
        try:
            resp = httpx.get(
                cfg.cohere_base_url.rstrip("/") + "/v1/models",
                headers={"Authorization": f"Bearer {cfg.cohere_api_key}"},
                timeout=10.0,
            )
            if 200 <= resp.status_code < 300:
                data = resp.json()
                names = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return names or _COHERE_FALLBACK_MODELS
            return _COHERE_FALLBACK_MODELS
        except httpx.HTTPError:
            return _COHERE_FALLBACK_MODELS
    return []


# Recent Claude model IDs users are likely to pick. Used as a fallback when the
# /v1/models endpoint is gated or unavailable.
_ANTHROPIC_FALLBACK_MODELS = [
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-7-sonnet-latest",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-opus-latest",
]

_GEMINI_FALLBACK_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash-preview-05-20",
]

_COHERE_FALLBACK_MODELS = [
    "command-r-plus",
    "command-r",
    "command-r7b-12-2024",
    "command-r-08-2024",
    "command-r-plus-08-2024",
    "c4ai-aya-expanse-8b",
    "c4ai-aya-expanse-32b",
]


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
