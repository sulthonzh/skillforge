"""Tests for the Anthropic provider (native Messages API)."""

from __future__ import annotations

import json

import httpx
import pytest

from skillforge_api.services.ai_provider import (
    AIProviderError,
    AnthropicProvider,
    list_models,
    test_provider_connection as _test_connection,
)
from skillforge_api.services.user_config import ProviderConfig


def _mock_transport(handler):
    """Build an httpx.MockTransport from a handler(request) -> Response.

    MockTransport attaches the request to the response, so raise_for_status()
    works — unlike a bare httpx.Response(status, json=...).
    """
    return httpx.MockTransport(handler)


def _resp(request, status, body):
    return httpx.Response(status_code=status, json=body, request=request)


class _Recorder:
    """Captures the last request seen by the transport for assertions."""

    def __init__(self):
        self.last = None


def test_anthropic_requires_api_key():
    with pytest.raises(AIProviderError):
        AnthropicProvider(api_key="")


def test_anthropic_complete_sends_native_format():
    """Anthropic expects system as a top-level field and x-api-key auth."""
    rec = _Recorder()

    def handler(request):
        rec.last = request
        return _resp(request, 200, {"content": [{"type": "text", "text": '{"reply":"ok"}'}]})

    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest")
    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest", transport=_mock_transport(handler))

    out = provider.complete("SYSTEM PROMPT", "user message", json_mode=True)

    assert json.loads(out) == {"reply": "ok"}
    # URL is the Messages endpoint.
    assert str(rec.last.url).endswith("/v1/messages")
    # Auth via x-api-key (NOT Bearer), and the version header is present.
    assert rec.last.headers["x-api-key"] == "sk-ant-test"
    assert rec.last.headers["anthropic-version"] == "2023-06-01"
    payload = json.loads(rec.last.content)
    # System is top-level, not a message role.
    assert payload["system"] == "SYSTEM PROMPT"
    assert [m["role"] for m in payload["messages"]] == ["user"]
    # json_mode appends a JSON-only instruction to the user content.
    assert "JSON" in payload["messages"][0]["content"]


def test_anthropic_complete_json_round_trip():
    body = {"content": [{"type": "text", "text": '{"skill_name":"x-y","tools":[]}'}]}

    def handler(request):
        return _resp(request, 200, body)

    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest")
    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest", transport=_mock_transport(handler))
    parsed = provider.complete_json("sys", "usr")
    assert parsed == {"skill_name": "x-y", "tools": []}


def test_anthropic_strips_code_fences():
    body = {"content": [{"type": "text", "text": '```json\n{"a":1}\n```'}]}

    def handler(request):
        return _resp(request, 200, body)

    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest")
    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest", transport=_mock_transport(handler))
    parsed = provider.complete_json("sys", "usr")
    assert parsed == {"a": 1}


def test_anthropic_raises_on_http_error():
    def handler(request):
        return _resp(request, 401, {"type": "error", "error": {"message": "bad key"}})

    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest")
    provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-latest", transport=_mock_transport(handler))
    with pytest.raises(AIProviderError):
        provider.complete("s", "u")


def test_test_connection_anthropic_requires_key():
    cfg = ProviderConfig(provider="anthropic", anthropic_api_key="", anthropic_base_url="https://api.anthropic.com")
    r = _test_connection(cfg)
    assert r["ok"] is False
    assert "key" in r["detail"].lower()


def test_test_connection_anthropic_401_message():
    cfg = ProviderConfig(
        provider="anthropic",
        anthropic_api_key="dummy",
        anthropic_base_url="https://api.anthropic.com",
        model="claude-3-5-haiku-latest",
    )

    # Patch httpx.post used by test_provider_connection to return 401.
    import skillforge_api.services.ai_provider as mod

    orig = mod.httpx.post

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(401, json={"error": "auth"})

    mod.httpx.post = fake_post  # type: ignore[attr-defined]
    try:
        r = _test_connection(cfg)
    finally:
        mod.httpx.post = orig  # type: ignore[attr-defined]
    assert r["ok"] is False
    assert "401" in r["detail"]


def test_test_connection_anthropic_success():
    cfg = ProviderConfig(
        provider="anthropic",
        anthropic_api_key="dummy",
        anthropic_base_url="https://api.anthropic.com",
        model="claude-3-5-haiku-latest",
    )

    import skillforge_api.services.ai_provider as mod

    orig = mod.httpx.post

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(200, json={"content": [{"type": "text", "text": "."}]})

    mod.httpx.post = fake_post  # type: ignore[attr-defined]
    try:
        r = _test_connection(cfg)
    finally:
        mod.httpx.post = orig  # type: ignore[attr-defined]
    assert r["ok"] is True


def test_list_models_anthropic_falls_back():
    cfg = ProviderConfig(
        provider="anthropic",
        anthropic_api_key="",
        anthropic_base_url="https://api.anthropic.com",
    )
    models = list_models(cfg)
    assert "claude-3-5-sonnet-latest" in models
    assert len(models) >= 3


def test_anthropic_registered_in_factory():
    """get_provider_for_config must build an AnthropicProvider for anthropic configs."""
    from skillforge_api.services.ai_provider import get_provider_for_config

    cfg = ProviderConfig(
        provider="anthropic",
        anthropic_api_key="sk-ant-test",
        anthropic_base_url="https://api.anthropic.com",
        model="claude-3-5-sonnet-latest",
    )
    provider = get_provider_for_config(cfg)
    assert isinstance(provider, AnthropicProvider)


def test_anthropic_allowed_in_settings(monkeypatch):
    """The settings validator accepts 'anthropic' as a provider."""
    monkeypatch.setenv("SKILLFORGE_AI_PROVIDER", "anthropic")
    from skillforge_api.settings import Settings

    s = Settings()
    assert s.ai_provider == "anthropic"
