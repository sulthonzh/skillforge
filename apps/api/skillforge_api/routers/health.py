"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe. Returns ``{"status": "ok", "version": ...}``."""
    return {"status": "ok", "version": __version__}
