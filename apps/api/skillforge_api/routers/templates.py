"""Templates router.

Exposes the bundled Jinja2 template names and the raw tool catalog so the Web
UI can show "what's available" without hardcoding anything.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..services.tool_catalog import get_catalog

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("/catalog")
async def get_tool_catalog() -> dict:
    """Return the raw tool catalog (domains + recommended tools)."""
    catalog = get_catalog()
    return {"schema_version": "1.0", "domains": catalog.domains}


@router.get("/domains")
async def get_domains() -> dict:
    """Return just the domain keys and labels."""
    catalog = get_catalog()
    return {
        "domains": [
            {"key": key, "label": entry.get("label", key)}
            for key, entry in catalog.domains.items()
        ]
    }
