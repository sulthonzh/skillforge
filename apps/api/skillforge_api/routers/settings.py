"""Settings router — mutable AI provider configuration.

Endpoints:
    GET    /api/settings/provider        → current provider config (key masked)
    PUT    /api/settings/provider        → update provider config (persisted)
    POST   /api/settings/provider/test   → liveness probe for the *current* config
    GET    /api/settings/models          → available models for the current provider
    GET    /api/settings/providers       → the allowed provider list
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..settings import get_settings
from ..services.ai_provider import (
    AIProviderError,
    list_models,
    test_provider_connection,
)
from ..services.user_config import (
    ProviderConfig,
    get_user_config_store,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class ProviderUpdate(BaseModel):
    """Subset of fields the UI may send. Empty/absent fields are left unchanged."""

    provider: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str | None = None
    anthropic_base_url: str | None = None
    anthropic_api_key: str | None = None
    gemini_base_url: str | None = None
    gemini_api_key: str | None = None
    cohere_base_url: str | None = None
    cohere_api_key: str | None = None
    model: str | None = None


class TestRequest(BaseModel):
    """Optional inline config to test without persisting.

    If all fields are empty, the currently-persisted config is tested.
    """

    provider: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str | None = None
    anthropic_base_url: str | None = None
    anthropic_api_key: str | None = None
    gemini_base_url: str | None = None
    gemini_api_key: str | None = None
    cohere_base_url: str | None = None
    cohere_api_key: str | None = None
    model: str | None = None


_ALLOWED = ["mock", "openai-compatible", "ollama-local", "anthropic", "gemini", "cohere"]

# Presets for OpenAI-compatible providers — same wire protocol, different base
# URLs/models. The UI uses these to pre-fill the base URL + a default model when
# the user picks a hosted provider.
_OPENAI_COMPAT_PRESETS = [
    {
        "key": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1",
        "docs_url": "https://platform.openai.com/api-keys",
    },
    {
        "key": "openrouter",
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "docs_url": "https://openrouter.ai/keys",
    },
    {
        "key": "groq",
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "docs_url": "https://console.groq.com/keys",
    },
    {
        "key": "together",
        "label": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "docs_url": "https://api.together.xyz/settings/api-keys",
    },
    {
        "key": "mistral",
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "docs_url": "https://console.mistral.ai/api-keys",
    },
    {
        "key": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "docs_url": "https://platform.deepseek.com/api_keys",
    },
    {
        "key": "xai",
        "label": "xAI (Grok)",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-3-mini",
        "docs_url": "https://console.x.ai",
    },
    {
        "key": "fireworks",
        "label": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "docs_url": "https://fireworks.ai/account/api-keys",
    },
    {
        "key": "zai",
        "label": "Z.ai (GLM)",
        "base_url": "https://api.z.ai/api/coding/paas/v4",
        "default_model": "glm-4.6",
        "docs_url": "https://z.ai",
    },
]


def _to_cfg(payload: ProviderUpdate | TestRequest, fallback: ProviderConfig) -> ProviderConfig:
    """Build a ProviderConfig from a partial payload, filling gaps from *fallback*."""
    return ProviderConfig(
        provider=(payload.provider or fallback.provider),
        openai_base_url=(payload.openai_base_url or fallback.openai_base_url),
        # For "test" we allow inheriting the stored key when the payload omits it.
        openai_api_key=(payload.openai_api_key or fallback.openai_api_key),
        ollama_base_url=(payload.ollama_base_url or fallback.ollama_base_url),
        anthropic_base_url=(payload.anthropic_base_url or fallback.anthropic_base_url),
        anthropic_api_key=(payload.anthropic_api_key or fallback.anthropic_api_key),
        gemini_base_url=(payload.gemini_base_url or fallback.gemini_base_url),
        gemini_api_key=(payload.gemini_api_key or fallback.gemini_api_key),
        cohere_base_url=(payload.cohere_base_url or fallback.cohere_base_url),
        cohere_api_key=(payload.cohere_api_key or fallback.cohere_api_key),
        model=(payload.model or fallback.model),
    )


@router.get("/providers")
async def list_providers() -> dict:
    return {"providers": _ALLOWED}


@router.get("/presets")
async def list_presets() -> dict:
    """Return OpenAI-compatible provider presets (base URL + default model).

    The UI uses these to pre-fill the OpenAI-compatible form when a user picks a
    hosted provider (OpenAI, OpenRouter, Groq, Together, Mistral, …). They all
    speak the same wire protocol; only the base URL + default model differ.
    """
    return {"presets": _OPENAI_COMPAT_PRESETS}


@router.get("/provider")
async def get_provider_config() -> dict:
    """Return the configured provider config PLUS the effective provider + degradation status.

    The extra ``effective``, ``degraded``, and ``fallback_reason`` fields let
    the UI warn the user when their configured provider failed to initialize
    (e.g. missing API key) and the app silently fell back to mock. Without this,
    users got heuristic mock output thinking it was AI-generated.
    """
    cfg = get_user_config_store().get_provider()
    data = cfg.masked()
    # Merge in the effective-provider signal so the UI can show a warning.
    from ..services.ai_provider import get_provider_status

    status = get_provider_status()
    data["effective"] = status["effective"]
    data["degraded"] = status["degraded"]
    data["fallback_reason"] = status["fallback_reason"]
    return data


@router.put("/provider")
async def update_provider_config(update: ProviderUpdate) -> dict:
    if update.provider and update.provider not in _ALLOWED:
        raise HTTPException(400, f"Unknown provider: {update.provider!r}")
    try:
        cfg = get_user_config_store().set_provider(update.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"saved": True, "provider": cfg.masked()}


@router.post("/provider/test")
async def test_provider(req: TestRequest) -> dict:
    """Test a provider config. If the body is empty, test the stored config.

    Offloaded to a threadpool: test_provider_connection makes blocking HTTP
    calls (/models + chat probe). (Tier 0.1.)
    """
    stored = get_user_config_store().get_provider()
    cfg = _to_cfg(req, stored)
    return await run_in_threadpool(test_provider_connection, cfg)


@router.get("/models")
async def get_models() -> dict:
    """List models available to the current provider (best-effort).

    Offloaded to a threadpool: list_models makes a blocking /models HTTP call.
    (Tier 0.1.)
    """
    cfg = get_user_config_store().get_provider()
    try:
        models = await run_in_threadpool(list_models, cfg)
        return {"provider": cfg.provider, "models": models}
    except AIProviderError as exc:
        return {"provider": cfg.provider, "models": [], "error": str(exc)}


@router.get("/paths")
async def get_paths() -> dict:
    """Return the actually-configured local paths.

    The UI uses this so it never shows a hardcoded ``~/.skillforge/skills`` that
    might contradict the configured ``SKILLFORGE_SKILLS_DIR``.
    """
    settings = get_settings()
    store = get_user_config_store()
    return {
        "skills_dir": str(settings.skills_dir),
        "config_path": str(store.path),
        "db_path": str(settings.db_path),
    }
