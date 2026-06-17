"""Tests for the Gemini and Cohere providers (native APIs)."""

from __future__ import annotations

import json

import httpx
import pytest

from skillforge_api.services.ai_provider import (
    AIProviderError,
    CohereProvider,
    GeminiProvider,
    list_models,
)
from skillforge_api.services.user_config import ProviderConfig


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _resp(request, status, body):
    return httpx.Response(status_code=status, json=body, request=request)


class _Recorder:
    def __init__(self):
        self.last = None


# ---- Gemini ----


def test_gemini_requires_api_key():
    with pytest.raises(AIProviderError):
        GeminiProvider(api_key="")


def test_gemini_complete_native_shape():
    """Gemini: model in URL path, systemInstruction top-level, x-goog-api-key auth."""
    rec = _Recorder()

    def handler(request):
        rec.last = request
        return _resp(
            request,
            200,
            {"candidates": [{"content": {"parts": [{"text": '{"reply":"ok"}'}]}}]},
        )

    provider = GeminiProvider(
        api_key="AIza-test", model="gemini-1.5-flash", transport=_mock_transport(handler)
    )
    out = provider.complete("SYSTEM", "hello", json_mode=True)

    assert json.loads(out) == {"reply": "ok"}
    # Model is in the URL path.
    assert "models/gemini-1.5-flash:generateContent" in str(rec.last.url)
    # Auth via x-goog-api-key.
    assert rec.last.headers["x-goog-api-key"] == "AIza-test"
    payload = json.loads(rec.last.content)
    # System is a top-level systemInstruction, not a contents role.
    assert payload["systemInstruction"]["parts"]["text"] == "SYSTEM"
    assert [c["role"] for c in payload["contents"]] == ["user"]


def test_gemini_json_round_trip():
    body = {"candidates": [{"content": {"parts": [{"text": '{"skill_name":"x","tools":[]}'}]}}]}

    def handler(request):
        return _resp(request, 200, body)

    provider = GeminiProvider(api_key="k", model="gemini-1.5-flash", transport=_mock_transport(handler))
    assert provider.complete_json("s", "u") == {"skill_name": "x", "tools": []}


def test_gemini_raises_on_http_error():
    def handler(request):
        return _resp(request, 403, {"error": {"message": "forbidden"}})

    provider = GeminiProvider(api_key="k", model="gemini-1.5-flash", transport=_mock_transport(handler))
    with pytest.raises(AIProviderError):
        provider.complete("s", "u")


def test_gemini_registered_in_factory():
    from skillforge_api.services.ai_provider import get_provider_for_config

    cfg = ProviderConfig(
        provider="gemini",
        gemini_base_url="https://generativelanguage.googleapis.com",
        gemini_api_key="AIza-test",
        model="gemini-1.5-flash",
    )
    assert isinstance(get_provider_for_config(cfg), GeminiProvider)


def test_gemini_list_models_fallback():
    cfg = ProviderConfig(provider="gemini", gemini_api_key="", gemini_base_url="https://x")
    models = list_models(cfg)
    assert "gemini-1.5-flash" in models
    assert "gemini-2.0-flash" in models


# ---- Cohere ----


def test_cohere_requires_api_key():
    with pytest.raises(AIProviderError):
        CohereProvider(api_key="")


def test_cohere_complete_native_shape():
    """Cohere: Bearer auth, top-level message + preamble (system), /v1/chat."""
    rec = _Recorder()

    def handler(request):
        rec.last = request
        return _resp(request, 200, {"text": '{"reply":"ok"}'})

    provider = CohereProvider(
        api_key="co-test", model="command-r-plus", transport=_mock_transport(handler)
    )
    out = provider.complete("SYSTEM", "hello", json_mode=True)

    assert json.loads(out) == {"reply": "ok"}
    assert str(rec.last.url).endswith("/v1/chat")
    assert rec.last.headers["Authorization"] == "Bearer co-test"
    payload = json.loads(rec.last.content)
    # Preamble carries the system prompt; message is the user input.
    assert payload["preamble"] == "SYSTEM"
    assert payload["message"] == "hello" or payload["message"].startswith("hello")
    assert payload["model"] == "command-r-plus"


def test_cohere_json_round_trip():
    body = {"text": '{"skill_name":"y","tools":[]}'}

    def handler(request):
        return _resp(request, 200, body)

    provider = CohereProvider(api_key="k", model="command-r-plus", transport=_mock_transport(handler))
    assert provider.complete_json("s", "u") == {"skill_name": "y", "tools": []}


def test_cohere_raises_on_http_error():
    def handler(request):
        return _resp(request, 401, {"message": "unauthorized"})

    provider = CohereProvider(api_key="k", model="command-r-plus", transport=_mock_transport(handler))
    with pytest.raises(AIProviderError):
        provider.complete("s", "u")


def test_cohere_registered_in_factory():
    from skillforge_api.services.ai_provider import get_provider_for_config

    cfg = ProviderConfig(
        provider="cohere",
        cohere_base_url="https://api.cohere.com",
        cohere_api_key="co-test",
        model="command-r-plus",
    )
    assert isinstance(get_provider_for_config(cfg), CohereProvider)


def test_cohere_list_models_fallback():
    cfg = ProviderConfig(provider="cohere", cohere_api_key="", cohere_base_url="https://x")
    models = list_models(cfg)
    assert "command-r-plus" in models
    assert "command-r" in models
