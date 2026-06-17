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
    model: str | None = None


class TestRequest(BaseModel):
    """Optional inline config to test without persisting.

    If all fields are empty, the currently-persisted config is tested.
    """

    provider: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str | None = None
    model: str | None = None


_ALLOWED = ["mock", "openai-compatible", "ollama-local"]


def _to_cfg(payload: ProviderUpdate | TestRequest, fallback: ProviderConfig) -> ProviderConfig:
    """Build a ProviderConfig from a partial payload, filling gaps from *fallback*."""
    return ProviderConfig(
        provider=(payload.provider or fallback.provider),
        openai_base_url=(payload.openai_base_url or fallback.openai_base_url),
        # For "test" we allow inheriting the stored key when the payload omits it.
        openai_api_key=(payload.openai_api_key or fallback.openai_api_key),
        ollama_base_url=(payload.ollama_base_url or fallback.ollama_base_url),
        model=(payload.model or fallback.model),
    )


@router.get("/providers")
async def list_providers() -> dict:
    return {"providers": _ALLOWED}


@router.get("/provider")
async def get_provider_config() -> dict:
    cfg = get_user_config_store().get_provider()
    return cfg.masked()


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
    """Test a provider config. If the body is empty, test the stored config."""
    stored = get_user_config_store().get_provider()
    cfg = _to_cfg(req, stored)
    return test_provider_connection(cfg)


@router.get("/models")
async def get_models() -> dict:
    """List models available to the current provider (best-effort)."""
    cfg = get_user_config_store().get_provider()
    try:
        return {"provider": cfg.provider, "models": list_models(cfg)}
    except AIProviderError as exc:
        return {"provider": cfg.provider, "models": [], "error": str(exc)}
