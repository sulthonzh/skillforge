"""Deploy router — symlink/copy skills to AI coding tools' skill directories."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.skill_registry import SkillRegistry
from ..services.symlink_deploy import get_deployer, get_detector

router = APIRouter(prefix="/api/deploy", tags=["deploy"])


class DeployBody(BaseModel):
    skill_name: str
    target_key: str | None = None  # specific tool, or None for all installed
    method: str = "symlink"  # "symlink" | "copy"


class UndeployBody(BaseModel):
    skill_name: str
    target_key: str | None = None


@router.get("/targets")
async def list_targets():
    """List all known AI tool targets with install status."""
    targets = get_detector().detect()
    return {
        "targets": [
            {
                "key": t.key,
                "label": t.label,
                "skills_dir": str(t.skills_dir),
                "installed": t.installed,
            }
            for t in targets
        ]
    }


@router.get("/{skill_name}/status")
async def deploy_status(skill_name: str):
    """Check which tools a skill is deployed to."""
    return {"skill_name": skill_name, "targets": get_deployer().status(skill_name)}


@router.post("/symlink")
async def deploy(body: DeployBody):
    """Symlink (or copy) a skill to one or all AI tool targets."""
    record = SkillRegistry().get(body.skill_name)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No installed skill named {body.skill_name!r}")
    result = get_deployer().deploy(
        skill_path=record.path,
        skill_name=body.skill_name,
        target_key=body.target_key,
        method=body.method,
    )
    return result


@router.post("/undeploy")
async def undeploy(body: UndeployBody):
    """Remove a skill symlink from one or all AI tool targets."""
    result = get_deployer().undeploy(body.skill_name, body.target_key)
    return result
