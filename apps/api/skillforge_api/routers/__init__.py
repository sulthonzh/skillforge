"""API routers."""

from . import (
    bridge as bridge_router,
    chat,
    eval as eval_router,
    health,
    marketplace as marketplace_router,
    registry,
    settings,
    skills,
    templates,
)

__all__ = [
    "bridge_router",
    "chat",
    "eval_router",
    "health",
    "marketplace_router",
    "registry",
    "settings",
    "skills",
    "templates",
]
