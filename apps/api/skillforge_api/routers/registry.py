"""Installed-skills registry router."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from ..schemas.manifest import (
    Architecture,
    Outputs,
    Safety,
    SkillAI,
    SkillManifest,
    SkillMeta,
    Tool,
)
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


def _load_manifest_from_dir(skill_dir: Path) -> SkillManifest:
    """Reconstruct a SkillManifest from an installed skill's config.yaml."""
    config_path = skill_dir / "config.yaml"
    if not config_path.is_file():
        raise HTTPException(409, f"Installed skill has no config.yaml at {config_path}.")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise HTTPException(500, f"{config_path} is not a mapping.")

    skill_raw = raw.get("skill") or {}
    tools = [
        Tool(
            name=str(t.get("name", "")),
            category=str(t.get("category", "misc")),
            enabled=bool(t.get("enabled", True)),
            reason=str(t.get("reason", "")),
        )
        for t in (raw.get("tools") or [])
    ]
    arch = raw.get("architecture") or {}
    outputs = raw.get("outputs") or {}
    safety = raw.get("safety") or {}
    ai = raw.get("ai") or {}

    return SkillManifest(
        schema_version=str(raw.get("schema_version", "1.0")),
        skill=SkillMeta(
            name=str(skill_raw.get("name", "")),
            title=str(skill_raw.get("title", "")),
            domain=str(skill_raw.get("domain", "")),
            description=str(skill_raw.get("description", "")),
            version=str(skill_raw.get("version", "0.1.0")),
            status=str(skill_raw.get("status", "installed")),
        ),
        ai=SkillAI(
            generated_by=str(ai.get("generated_by", "skillforge")),
            planner_model=str(ai.get("planner_model", "")),
        ),
        tools=tools,
        architecture=Architecture(patterns=list(arch.get("patterns") or [])),
        workflow=list(raw.get("workflow") or []),
        best_practices=list(raw.get("best_practices") or []),
        output_standards=list(raw.get("output_standards") or []),
        outputs=Outputs(
            required_files=list(outputs.get("required_files") or ["SKILL.md", "README.md", "config.yaml"]),
            required_directories=list(outputs.get("required_directories") or ["prompts", "templates", "scripts", "examples"]),
        ),
        safety=Safety(
            auto_execute_scripts=bool(safety.get("auto_execute_scripts", False)),
            require_user_confirmation_before_install=bool(safety.get("require_user_confirmation_before_install", True)),
            allow_network_access=bool(safety.get("allow_network_access", False)),
        ),
        example_prompts=list(raw.get("example_prompts") or []),
        example_outputs=list(raw.get("example_outputs") or []),
    )


@router.get("/skills/{skill_name}/manifest", response_model=SkillManifest)
async def get_skill_manifest(skill_name: str) -> SkillManifest:
    """Return an installed skill's manifest, ready to edit in the builder."""
    registry = SkillRegistry()
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"No installed skill named {skill_name!r}.")
    return _load_manifest_from_dir(Path(skill.path))


@router.delete("/skills/{skill_name}", response_model=RegistryMutationResponse)
async def remove_skill(skill_name: str) -> RegistryMutationResponse:
    registry = SkillRegistry()
    removed = registry.remove(skill_name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"No installed skill named {skill_name!r}.")
    return RegistryMutationResponse(removed=True, name=skill_name)
