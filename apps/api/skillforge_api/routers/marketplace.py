"""Marketplace router — the LOCAL UI's interface to the marketplace.

No bridge token (the user IS local). These endpoints talk to the configured
marketplace adapter (LocalStub today). This is what the ``/marketplace`` page
calls to browse, publish, and install-from-marketplace.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..rate_limit import get_pairing_limiter
from ..schemas.manifest import SkillManifest
from ..services.marketplace.adapters import get_adapter
from ..services.marketplace.approvals import ApprovalStatus, get_approval_manager
from ..services.marketplace.packaging import PackagingError, SkillPackager
from ..services.marketplace.pairing import get_pairing_manager

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


def _client_key(request: Request) -> str:
    """A stable key per client for rate limiting.

    For a 127.0.0.1-bound server the client IP is always loopback, so we also
    fold in the Origin header — a browser-driven attacker has a distinct origin
    from the local UI, and this keeps a flood from one tab from locking out a
    legitimate pairing started from another.
    """
    ip = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "")
    return f"{ip}:{origin}"


# ---- search/browse ----


@router.get("/search")
async def search(q: str = Query(default=""), tags: str | None = Query(default=None)):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    results = get_adapter().search(q, tag_list)
    return {"results": [r.to_dict() for r in results], "count": len(results)}


@router.get("/listings/{listing_id}")
async def get_listing(listing_id: str):
    listing = get_adapter().get(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"No listing {listing_id!r}")
    return listing.to_dict()


# ---- publish ----


class PublishBody(BaseModel):
    skill_name: str
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    license: str = "MIT"
    price_usd: float = 0.0
    author: str = "you"


@router.post("/publish")
async def publish(body: PublishBody):
    """Package a local skill and publish it to the marketplace adapter."""
    try:
        package_bytes = SkillPackager().pack(body.skill_name)
    except PackagingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    listing = get_adapter().publish(
        skill_name=body.skill_name,
        package_bytes=package_bytes,
        listing_meta=body.model_dump(),
    )
    return {"published": True, "listing": listing.to_dict()}


# ---- install from marketplace ----


class InstallFromMarketBody(BaseModel):
    listing_id: str


@router.post("/install")
async def install_from_market(body: InstallFromMarketBody):
    """Download a skill from the marketplace and queue it for user approval.

    SkillForge never auto-installs from the marketplace without confirmation,
    so this creates a pending approval. The UI calls /pending/{id}/approve to
    finalize.
    """
    adapter = get_adapter()
    listing = adapter.get(body.listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"No listing {body.listing_id!r}")
    try:
        package_bytes = adapter.download(body.listing_id)
        _manifest, _files = SkillPackager().unpack(package_bytes)
    except (PackagingError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Build the approval from the unpacked manifest.
    from ..schemas.manifest import SkillManifest

    manifest = SkillManifest.model_validate_json(_manifest.model_dump_json())
    approval = get_approval_manager().create(
        skill_name=manifest.skill.name,
        manifest_json=manifest.model_dump_json(),
        source=f"marketplace:{body.listing_id}",
    )
    return {
        "installed": False,
        "pending_approval": approval.id,
        "listing": listing.to_dict(),
        "detail": "Queued for approval. Approve in the Marketplace page.",
    }


# ---- approvals (the local UI manages these) ----


@router.get("/pending")
async def list_pending():
    return {"pending": [a.to_dict() for a in get_approval_manager().list_pending()]}


class ApproveBody(BaseModel):
    overwrite: bool = True


@router.post("/pending/{approval_id}/approve")
async def approve_install(approval_id: str, body: ApproveBody):
    from ..services.skill_installer import SkillInstaller

    mgr = get_approval_manager()
    approval = mgr.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="No such approval")
    manifest = SkillManifest.model_validate_json(approval.manifest_json)
    try:
        outcome = SkillInstaller().install(manifest, overwrite=body.overwrite)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mgr.set_status(approval_id, ApprovalStatus.APPROVED)
    return {
        "installed": outcome.installed,
        "path": outcome.path,
        "new_version": outcome.new_version,
    }


@router.post("/pending/{approval_id}/reject")
async def reject_install(approval_id: str):
    mgr = get_approval_manager()
    if mgr.set_status(approval_id, ApprovalStatus.REJECTED) is None:
        raise HTTPException(status_code=404, detail="No such approval")
    return {"rejected": True}


# ---- pairing management (local UI generates codes + manages tokens) ----


@router.post("/pair/code")
async def generate_pair_code(request: Request):
    """Generate a pairing code for the marketplace website to present.

    Rate-limited to keep an attacker from flooding the store with pending codes
    or hammering the endpoint. The code itself is CSPRNG-generated and single-
    use; this is defense-in-depth.
    """
    if not get_pairing_limiter().allow(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many pairing attempts. Wait a minute and try again.",
        )
    code = get_pairing_manager().generate_code()
    return {"code": code, "ttl_minutes": 10}


@router.get("/tokens")
async def list_tokens():
    return {
        "tokens": [
            {
                "id": t.id,
                "label": t.label,
                "scopes": t.scopes,
                "created_at": t.created_at,
                "last_used_at": t.last_used_at,
                "revoked": t.revoked,
            }
            for t in get_pairing_manager().list_tokens()
        ]
    }


@router.delete("/tokens/{token_id}")
async def revoke_token(token_id: str):
    revoked = get_pairing_manager().revoke(token_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="No such token")
    return {"revoked": True, "id": token_id}
