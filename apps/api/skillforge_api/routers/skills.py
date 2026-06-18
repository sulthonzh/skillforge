"""Skill generation, preview, install, and validation endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..schemas.skill import (
    GeneratedFile,
    GenerateFilesRequest,
    GenerateFilesResponse,
    InstallRequest,
    InstallResponse,
    ValidateRequest,
    ValidateResponse,
    ValidationIssue,
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


# ---- Generated tool execution (opt-in, with consent) ----


class ToolPreviewResponse(BaseModel):
    script: str
    command: list[str]
    cwd: str
    runnable: bool
    reason: str = ""


class ToolRunRequest(BaseModel):
    confirm: bool = False
    args: str = ""


class ToolRunResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    command: list[str]


@router.get("/{skill_name}/tools", response_model=list[ToolPreviewResponse])
async def list_skill_tools(skill_name: str):
    """List the generated tool scripts available for a skill (with runnability)."""
    from ..services.skill_tools.executor import ExecutorError, ToolExecutor

    try:
        executor = ToolExecutor()
        from pathlib import Path

        from ..services.skill_registry import SkillRegistry

        record = SkillRegistry().get(skill_name)
        if record is None:
            raise HTTPException(status_code=404, detail=f"No installed skill named {skill_name!r}")
        tools_dir = Path(record.path) / "tools"
        if not tools_dir.is_dir():
            return []
        result = []
        for script_file in sorted(tools_dir.iterdir()):
            if script_file.is_file() and script_file.name not in ("Makefile",):
                preview = executor.preview(skill_name, script_file.name)
                result.append(ToolPreviewResponse(**preview.__dict__))
        return result
    except ExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{skill_name}/tools/{script}/preview", response_model=ToolPreviewResponse)
async def preview_tool(skill_name: str, script: str):
    """Dry-run preview of a generated tool — what would run, without running it."""
    from ..services.skill_tools.executor import ExecutorError, ToolExecutor

    try:
        preview = ToolExecutor().preview(skill_name, script)
        return ToolPreviewResponse(**preview.__dict__)
    except ExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{skill_name}/tools/{script}/run", response_model=ToolRunResponse)
async def run_tool(skill_name: str, script: str, req: ToolRunRequest):
    """Run a generated tool. Requires explicit confirmation."""
    from ..services.skill_tools.executor import ExecutorError, ToolExecutor

    try:
        result = ToolExecutor().run(skill_name, script, confirm=req.confirm, args=req.args)
        return ToolRunResponse(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            command=result.command,
        )
    except ExecutorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
