"""Skill generation, preview, install, and validation endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..schemas.skill import (
    GenerateFilesRequest,
    GenerateFilesResponse,
    GeneratedFile,
    InstallRequest,
    InstallResponse,
    ValidateRequest,
    ValidationIssue,
    ValidateResponse,
)
from ..services.skill_generator import SkillGenerator
from ..services.skill_installer import InstallerError, SkillInstaller
from ..services.skill_validator import SkillValidator

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.post("/preview", response_model=GenerateFilesResponse)
async def preview_skill(req: GenerateFilesRequest) -> GenerateFilesResponse:
    """Render the skill files for a manifest without writing to disk."""
    generator = SkillGenerator()
    files = generator.generate(req.manifest)
    return GenerateFilesResponse(files=[GeneratedFile(path=f.path, content=f.content) for f in files])


@router.post("/validate", response_model=ValidateResponse)
async def validate_skill(req: ValidateRequest) -> ValidateResponse:
    """Validate a manifest (optionally against generated preview files)."""
    generator = SkillGenerator()
    validator = SkillValidator()
    files = req.files or [GeneratedFile(path=f.path, content=f.content) for f in generator.generate(req.manifest)]
    files_for_validator = [GeneratedFile(path=f.path, content=f.content) for f in files]
    result = validator.validate_manifest(req.manifest, files_for_validator)
    return ValidateResponse(
        valid=result.valid,
        errors=[ValidationIssue(**i.to_dict()) for i in result.issues],
    )


@router.post("/install", response_model=InstallResponse)
async def install_skill(req: InstallRequest) -> InstallResponse:
    """Install a manifest's files into the local skills directory."""
    installer = SkillInstaller()
    try:
        outcome = installer.install(req.manifest, overwrite=req.overwrite)
    except InstallerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if outcome.skipped_existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A skill named {req.manifest.skill.name!r} is already installed at "
                f"{outcome.path}. Re-run with overwrite=true to replace it."
            ),
        )
    return InstallResponse(
        installed=outcome.installed,
        path=outcome.path,
        previous_version=outcome.previous_version,
        new_version=outcome.new_version,
        version_bump_level=outcome.version_bump.level if outcome.version_bump else None,
        version_bump_reason=outcome.version_bump.reason if outcome.version_bump else None,
    )
