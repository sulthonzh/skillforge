"""Bridge router — endpoints the marketplace website calls (token + scope gated).

All under ``/api/bridge``. The marketplace sends ``Authorization: Bearer <token>``
on every call. These never touch the main ``/api/*`` routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..rate_limit import get_pairing_limiter
from ..schemas.manifest import SkillManifest
from ..services.marketplace.approvals import ApprovalStatus, get_approval_manager
from ..services.marketplace.bridge import BridgePrincipal, require_bridge, require_scope
from ..services.marketplace.packaging import PackagingError, SkillPackager
from ..services.marketplace.pairing import get_pairing_manager
from ..services.skill_installer import SkillInstaller
from ..services.skill_registry import SkillRegistry

router = APIRouter(prefix="/api/bridge", tags=["bridge"])


def _client_key(request: Request) -> str:
    """Stable per-client key for rate limiting (see marketplace._client_key)."""
    ip = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "")
    return f"{ip}:{origin}"


# ---- pairing (no token yet — the code IS the auth) ----


class CompletePairingBody(BaseModel):
    code: str
    label: str = "marketplace"


@router.post("/pair/complete")
async def complete_pairing(body: CompletePairingBody, request: Request):
    """Exchange a pairing code for a bridge token. Single-use; 10-min TTL.

    Rate-limited: an attacker can't brute-force the 6-char code faster than
    10 attempts/minute, which makes the ~887M codespace unreachable in the
    10-minute code lifetime.
    """
    if not get_pairing_limiter().allow(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many pairing attempts. Wait a minute and try again.",
        )
    result = get_pairing_manager().complete_pairing(body.code)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid, expired, or used pairing code")
    plaintext, info = result
    return {
        "token": plaintext,
        "token_id": info.id,
        "scopes": info.scopes,
        "label": info.label,
        "expires_in": None,  # tokens don't expire (revoke to invalidate)
    }


@router.get("/whoami")
async def whoami(principal: BridgePrincipal = Depends(require_bridge)):
    """Validate a token. Returns the principal's scopes + label."""
    return {
        "token_id": principal.token_id,
        "label": principal.label,
        "scopes": principal.scopes,
    }


# ---- local registry (marketplace reads what's installed) ----


@router.get("/skills")
async def bridge_list_skills(principal: BridgePrincipal = Depends(require_scope("registry:read"))):
    skills = SkillRegistry().list_installed()
    return {
        "skills": [
            {"name": s.name, "version": s.version, "domain": s.domain}
            for s in skills
        ]
    }


# ---- publish (marketplace pulls a packaged skill from local) ----


class PublishBody(BaseModel):
    skill_name: str


@router.post("/skills/publish")
async def bridge_publish(
    body: PublishBody,
    principal: BridgePrincipal = Depends(require_scope("skills:publish")),
):
    """Package a local skill and push it to the configured marketplace adapter."""
    try:
        package_bytes = SkillPackager().pack(body.skill_name)
    except PackagingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # The adapter (stub today) stores it. In the real marketplace, this would
    # upload to the cloud.
    from ..services.marketplace.adapters import get_adapter

    listing = get_adapter().publish(
        skill_name=body.skill_name,
        package_bytes=package_bytes,
        listing_meta={"author": principal.label},
    )
    return {"published": True, "listing": listing.to_dict()}


# ---- install (marketplace pushes a skill to local — requires approval) ----


class BridgeInstallBody(BaseModel):
    manifest: SkillManifest
    unattended: bool = False


@router.post("/skills/install")
async def bridge_install(
    body: BridgeInstallBody,
    principal: BridgePrincipal = Depends(require_scope("skills:install")),
):
    """Install a skill from the marketplace. Requires user approval unless
    the token has ``skills:install:unattended`` AND body.unattended is True."""
    can_unattended = "skills:install:unattended" in principal.scopes
    if body.unattended and can_unattended:
        # Direct install (no approval queue) — e.g. trusted automation.
        try:
            outcome = SkillInstaller().install(body.manifest, overwrite=True)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"installed": outcome.installed, "path": outcome.path, "approved_automatically": True}

    # Default: create a pending approval for the user to confirm.
    import json

    approval = get_approval_manager().create(
        skill_name=body.manifest.skill.name,
        manifest_json=body.manifest.model_dump_json(),
        source=f"bridge:{principal.token_id}",
    )
    return {
        "installed": False,
        "pending_approval": approval.id,
        "detail": "Skill install queued for user approval.",
    }


# ---- approval queue (the local UI polls this) ----


@router.get("/pending")
async def bridge_pending(principal: BridgePrincipal = Depends(require_bridge)):
    return {"pending": [a.to_dict() for a in get_approval_manager().list_pending()]}


@router.post("/pending/{approval_id}/approve")
async def bridge_approve(approval_id: str, principal: BridgePrincipal = Depends(require_bridge)):
    mgr = get_approval_manager()
    approval = mgr.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="No such approval")
    import json
    from ..schemas.manifest import SkillManifest

    manifest = SkillManifest.model_validate_json(approval.manifest_json)
    try:
        outcome = SkillInstaller().install(manifest, overwrite=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mgr.set_status(approval_id, ApprovalStatus.APPROVED)
    return {"installed": outcome.installed, "path": outcome.path}


@router.post("/pending/{approval_id}/reject")
async def bridge_reject(approval_id: str, principal: BridgePrincipal = Depends(require_bridge)):
    mgr = get_approval_manager()
    if mgr.set_status(approval_id, ApprovalStatus.REJECTED) is None:
        raise HTTPException(status_code=404, detail="No such approval")
    return {"rejected": True}
