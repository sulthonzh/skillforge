"""Tests for the split HTTP timeout and eval context truncation.

These guard the fix for the eval-harness read-timeout regression on slow
providers (e.g. Z.ai/GLM), where a flat 60s timeout was too short when the
full SKILL.md was sent as system context.
"""

from __future__ import annotations

import httpx
import pytest

from skillforge_api.settings import reload_settings
from skillforge_api.services.ai_provider import (
    AnthropicProvider,
    CohereProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
    _format_http_error,
)
from skillforge_api.services.eval.runner import EvalRunner


# ---------------------------------------------------------------------------
# Settings → httpx.Timeout
# ---------------------------------------------------------------------------


def test_settings_http_timeout_is_split():
    s = reload_settings()
    s.request_connect_timeout = 7.0
    s.request_read_timeout = 99.0
    s.request_write_timeout = 12.0
    s.request_pool_timeout = 8.0
    t = s.http_timeout
    assert isinstance(t, httpx.Timeout)
    # httpx.Timeout exposes the per-phase limits as attributes.
    assert t.connect == pytest.approx(7.0)
    assert t.read == pytest.approx(99.0)
    assert t.write == pytest.approx(12.0)
    assert t.pool == pytest.approx(8.0)


def test_settings_http_timeout_defaults_are_generous():
    """Defaults must give slow providers enough headroom (the bug we fixed)."""
    s = reload_settings()
    # The old flat default was 60s; the new read default must be >= 60s.
    assert s.request_read_timeout >= 60.0
    assert s.request_connect_timeout <= 30.0  # connect should still fail fast


# ---------------------------------------------------------------------------
# Providers use the split timeout
# ---------------------------------------------------------------------------


def _capture_timeout(monkeypatch):
    """Patch httpx.post to record the timeout argument it was called with.

    Returns a single response shape that satisfies all provider parsers, keyed
    off the URL path (each provider posts to a distinct path).
    """
    captured: dict = {}

    def fake_post(url, headers=None, json=None, body=None, timeout=None, **kw):
        captured["timeout"] = timeout

        class _R:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                u = str(url)
                if "chat/completions" in u:
                    return {"choices": [{"message": {"content": "ok"}}]}
                if "/v1/messages" in u:  # Anthropic
                    return {"content": [{"type": "text", "text": "ok"}]}
                if "generateContent" in u:  # Gemini
                    return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
                if "/v1/chat" in u:  # Cohere
                    return {"text": "ok"}
                return {}

        return _R()

    monkeypatch.setattr("skillforge_api.services.ai_provider.httpx.post", fake_post)
    return captured


def test_openai_provider_uses_split_timeout(monkeypatch):
    captured = _capture_timeout(monkeypatch)
    p = OpenAICompatibleProvider(
        base_url="https://example.com/v1", api_key="k", model="m"
    )
    p.complete("s", "u")
    assert isinstance(captured["timeout"], httpx.Timeout)
    assert captured["timeout"].read >= 60.0  # generous, not the old flat 60s


def test_anthropic_provider_uses_split_timeout(monkeypatch):
    captured = _capture_timeout(monkeypatch)
    p = AnthropicProvider(
        base_url="https://example.com", api_key="k", model="m"
    )
    p.complete("s", "u")
    assert isinstance(captured["timeout"], httpx.Timeout)


def test_gemini_provider_uses_split_timeout(monkeypatch):
    captured = _capture_timeout(monkeypatch)
    p = GeminiProvider(base_url="https://example.com", api_key="k", model="m")
    p.complete("s", "u")
    assert isinstance(captured["timeout"], httpx.Timeout)


def test_cohere_provider_uses_split_timeout(monkeypatch):
    captured = _capture_timeout(monkeypatch)
    p = CohereProvider(base_url="https://example.com", api_key="k", model="m")
    p.complete("s", "u")
    assert isinstance(captured["timeout"], httpx.Timeout)


# ---------------------------------------------------------------------------
# Error message is actionable on timeout
# ---------------------------------------------------------------------------


def test_format_http_error_timeout_message_mentions_env_var():
    err = httpx.ReadTimeout("read timed out")
    msg = _format_http_error("OpenAI-compatible", err)
    # The message should hint at the env var a user can raise.
    assert "timed out" in msg.lower()
    assert "SKILLFORGE_REQUEST_READ_TIMEOUT" in msg


def test_format_http_error_connect_message_is_distinct():
    err = httpx.ConnectError("no route to host")
    msg = _format_http_error("Anthropic", err)
    assert "connection failed" in msg.lower()
    assert "base URL" in msg or "reachable" in msg


# ---------------------------------------------------------------------------
# Eval context truncation
# ---------------------------------------------------------------------------


def test_eval_runner_truncates_large_skill_context(monkeypatch):
    s = reload_settings()
    s.eval_context_max_chars = 200
    runner = EvalRunner(provider=None)  # uses mock provider by default

    big = "HEADER\n" + ("line of skill content\n" * 200)
    truncated = runner._truncate_context(big)
    assert len(truncated) <= 200 + 80  # head + truncation marker
    assert "truncated" in truncated.lower()


def test_eval_runner_keeps_small_skill_context(monkeypatch):
    s = reload_settings()
    s.eval_context_max_chars = 4000
    runner = EvalRunner(provider=None)

    small = "# Title\nshort skill body\n"
    assert runner._truncate_context(small) == small  # unchanged
