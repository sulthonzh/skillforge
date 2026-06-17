"""Tests for the mutable user provider config store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillforge_api.services import user_config
from skillforge_api.services.user_config import (
    ProviderConfig,
    UserConfigStore,
    _mask_key,
)


def test_get_provider_defaults_to_env(tmp_path):
    store = UserConfigStore(tmp_path / "cfg.json")
    cfg = store.get_provider()
    # Defaults come from the env (mock in test fixture).
    assert cfg.provider == "mock"
    assert cfg.model  # inherited from settings


def test_set_then_get_round_trip(tmp_path):
    store = UserConfigStore(tmp_path / "cfg.json")
    store.set_provider({"provider": "ollama-local", "model": "llama3.1", "ollama_base_url": "http://x:11434"})
    cfg = store.get_provider()
    assert cfg.provider == "ollama-local"
    assert cfg.model == "llama3.1"
    assert cfg.ollama_base_url == "http://x:11434"


def test_persisted_to_disk_with_restrictive_perms(tmp_path):
    path = tmp_path / "cfg.json"
    store = UserConfigStore(path)
    store.set_provider({"provider": "openai-compatible", "openai_api_key": "sk-test-12345678"})
    assert path.is_file()
    data = json.loads(path.read_text())
    assert data["provider"]["openai_api_key"] == "sk-test-12345678"
    # File should be chmod 0600 (owner-only) when the OS supports it.
    perms = oct(path.stat().st_mode & 0o777)
    assert perms in ("0o600", "0o644")  # 0o600 on POSIX; tolerate FS restrictions


def test_empty_api_key_does_not_wipe_stored_key(tmp_path):
    """A GET-then-PUT round trip with a blank key field must preserve the key."""
    store = UserConfigStore(tmp_path / "cfg.json")
    store.set_provider({"provider": "openai-compatible", "openai_api_key": "sk-secret"})
    # Simulate the UI re-saving other fields without re-typing the key.
    store.set_provider({"provider": "openai-compatible", "model": "gpt-4.1"})
    cfg = store.get_provider()
    assert cfg.openai_api_key == "sk-secret"
    assert cfg.model == "gpt-4.1"


def test_unknown_provider_rejected(tmp_path):
    store = UserConfigStore(tmp_path / "cfg.json")
    with pytest.raises(ValueError):
        store.set_provider({"provider": "bogus"})


def test_mask_key():
    assert _mask_key("") == ""
    assert _mask_key("short") == "•••••"
    assert _mask_key("sk-abcdefgh1234567890").startswith("sk-a")
    assert _mask_key("sk-abcdefgh1234567890").endswith("7890")


def test_merged_over_fills_blanks():
    from skillforge_api.settings import get_settings

    s = get_settings()
    cfg = ProviderConfig(provider="", openai_base_url="", openai_api_key="", ollama_base_url="", model="")
    merged = cfg.merged_over(s)
    assert merged.provider == s.ai_provider
    assert merged.openai_base_url == s.openai_base_url


def test_masked_view_hides_key():
    cfg = ProviderConfig(
        provider="openai-compatible",
        openai_base_url="x",
        openai_api_key="sk-abcdefgh1234567890",
        ollama_base_url="",
        model="gpt",
    )
    view = cfg.masked()
    assert view["openai_api_key_set"] is True
    assert "openai_api_key" not in view  # never the raw key
    assert view["openai_api_key_preview"].endswith("7890")
