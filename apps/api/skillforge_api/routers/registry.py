"""Installed-skills registry router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.registry import InstalledSkill, RegistryListResponse, RegistryMutationResponse
from ..services.skill_registry import SkillRegistry

router = APIRouter(prefix="/api/registry", tags=["registry"])


@router.get("/skills", response_model=RegistryListResponse)
async def list_skills() -> RegistryListResponse:
    registry = SkillRegistry()
    return RegistryListResponse(skills=registry.list_installed())


@router.get("/skills/{skill_name}", response_model=InstalledSkill)
async def get_skill(skill_name: str) -> InstalledSkill:
    registry = SkillRegistry()
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"No installed skill named {skill_name!r}.")
    return skill


@router.delete("/skills/{skill_name}", response_model=RegistryMutationResponse)
async def remove_skill(skill_name: str) -> RegistryMutationResponse:
    registry = SkillRegistry()
    removed = registry.remove(skill_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No installed skill named {skill_name!r}.")
    return RegistryMutationResponse(removed=True, name=skill_name)
