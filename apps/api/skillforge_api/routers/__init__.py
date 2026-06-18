"""API routers."""

from . import (
    bridge as bridge_router,
)
from . import (
    chat,
    health,
    registry,
    settings,
    skills,
    templates,
)
from . import (
    deploy as deploy_router,
)
from . import (
    eval as eval_router,
)
from . import (
    marketplace as marketplace_router,
)

__all__ = [
    "bridge_router",
    "chat",
    "deploy_router",
    "eval_router",
    "health",
    "marketplace_router",
    "registry",
    "settings",
    "skills",
    "templates",
]
