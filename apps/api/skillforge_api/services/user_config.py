"""Mutable user-provider configuration.

The env-driven :class:`Settings` is the *floor* (defaults / CI / secrets that
shouldn't be editable from a UI). This module adds a user-facing config layer
persisted at ``~/.skillforge/config.json`` that overrides provider settings at
runtime, so users can pick a provider and enter a key from the Web UI without
restarting the server.

Precedence when resolving the *active* provider config:
    user config file  >  environment (Settings)  >  hardcoded defaults

Only provider-related fields are mutable from the UI; everything else stays on
``Settings``. The API key, when set via the UI, is written to the file with
``0600`` perms and never logged.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel, Field

from ..settings import Settings, get_settings

# Fields the UI is allowed to read/write. The API key is write-only over the
# wire (GET returns a masked preview, never the full secret).
_ALLOWED_PROVIDERS = ("mock", "openai-compatible", "ollama-local", "anthropic")


class ProviderConfig(BaseModel):
    """The user-editable slice of provider configuration."""

    provider: str = Field(default="mock")
    openai_base_url: str = Field(default="")
    openai_api_key: str = Field(default="")
    ollama_base_url: str = Field(default="")
    anthropic_base_url: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    model: str = Field(default="")

    def merged_over(self, settings: Settings) -> "ProviderConfig":
        """Return a copy with empty fields filled from *settings* (the env floor)."""
        return ProviderConfig(
            provider=self.provider or settings.ai_provider,
            openai_base_url=self.openai_base_url or settings.openai_base_url,
            openai_api_key=self.openai_api_key or settings.openai_api_key,
            ollama_base_url=self.ollama_base_url or settings.ollama_base_url,
            anthropic_base_url=self.anthropic_base_url or getattr(settings, "anthropic_base_url", "https://api.anthropic.com"),
            anthropic_api_key=self.anthropic_api_key or getattr(settings, "anthropic_api_key", ""),
            model=self.model or settings.model,
        )

    def masked(self) -> dict[str, Any]:
        """A JSON-safe view for GET responses (API keys masked)."""
        return {
            "provider": self.provider,
            "openai_base_url": self.openai_base_url,
            "openai_api_key_set": bool(self.openai_api_key),
            "openai_api_key_preview": _mask_key(self.openai_api_key),
            "ollama_base_url": self.ollama_base_url,
            "anthropic_base_url": self.anthropic_base_url,
            "anthropic_api_key_set": bool(self.anthropic_api_key),
            "anthropic_api_key_preview": _mask_key(self.anthropic_api_key),
            "model": self.model,
        }


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return key[:4] + "…" + key[-4:]


class UserConfigStore:
    """Thread-safe JSON store for mutable user preferences."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._path = Path(path)
        else:
            self._path = Path.home() / ".skillforge" / "config.json"
        self._lock = RLock()
        self._cache: dict[str, Any] | None = None

    @property
    def path(self) -> Path:
        return self._path

    # ---- read ----
    def read_all(self) -> dict[str, Any]:
        with self._lock:
            if self._cache is None:
                self._cache = self._read_disk()
            # Return a shallow copy so callers can't mutate the cache.
            return dict(self._cache)

    def _read_disk(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def get_provider(self) -> ProviderConfig:
        """Return the user-configured provider, merged over the env floor."""
        data = self.read_all().get("provider", {})
        if not isinstance(data, dict):
            data = {}
        cfg = ProviderConfig(
            provider=str(data.get("provider", "")),
            openai_base_url=str(data.get("openai_base_url", "")),
            openai_api_key=str(data.get("openai_api_key", "")),
            ollama_base_url=str(data.get("ollama_base_url", "")),
            anthropic_base_url=str(data.get("anthropic_base_url", "")),
            anthropic_api_key=str(data.get("anthropic_api_key", "")),
            model=str(data.get("model", "")),
        )
        return cfg.merged_over(get_settings())

    # ---- write ----
    def set_provider(self, update: dict[str, Any]) -> ProviderConfig:
        """Merge *update* into the persisted provider config and return the result.

        Only known fields are accepted; ``provider`` must be one of the allowed
        values. An empty API key field is treated as "leave unchanged" so a
        GET-then-PUT round trip doesn't wipe a stored key.
        """
        current = self.read_all()
        provider_section = current.get("provider", {})
        if not isinstance(provider_section, dict):
            provider_section = {}

        new_provider = str(update.get("provider", "")).strip()
        if new_provider and new_provider not in _ALLOWED_PROVIDERS:
            raise ValueError(f"Unknown provider: {new_provider!r}")

        for field in (
            "provider",
            "openai_base_url",
            "ollama_base_url",
            "anthropic_base_url",
            "model",
        ):
            val = update.get(field)
            if val is not None and str(val).strip() != "":
                provider_section[field] = str(val).strip()

        # API keys: empty string means "don't touch"; explicit "" handled above.
        for key_field in ("openai_api_key", "anthropic_api_key"):
            key = update.get(key_field)
            if key is not None and str(key) != "":
                provider_section[key_field] = str(key)

        provider_section["updated_at"] = datetime.now(timezone.utc).isoformat()
        current["provider"] = provider_section
        self._write_disk(current)
        # Bust cache so the next read picks up the new value.
        with self._lock:
            self._cache = None
        return self.get_provider()

    def _write_disk(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        payload = json.dumps(data, indent=2, default=str)
        tmp.write_text(payload, encoding="utf-8")
        # Restrict perms — the file may contain an API key.
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self._path)
        # Ensure the final file is also restricted (replace copies perms on Unix
        # but be explicit for non-tmp cases).
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    def reset_cache(self) -> None:
        """Force the next read to hit disk (used by tests)."""
        with self._lock:
            self._cache = None


# ---- process-wide singleton (cache the store, not the data) ----
_store: UserConfigStore | None = None


def get_user_config_store() -> UserConfigStore:
    global _store
    if _store is None:
        _store = UserConfigStore()
    return _store


def set_user_config_store(store: UserConfigStore | None) -> None:
    """Override the singleton (tests pass a temp-dir store)."""
    global _store
    _store = store
