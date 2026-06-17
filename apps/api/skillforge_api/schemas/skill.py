"""Skill generation, install, and validation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .manifest import SkillManifest


class GenerateFilesRequest(BaseModel):
    manifest: SkillManifest


class GeneratedFile(BaseModel):
    path: str
    content: str


class GenerateFilesResponse(BaseModel):
    files: list[GeneratedFile]


class InstallRequest(BaseModel):
    manifest: SkillManifest
    overwrite: bool = False


class InstallResponse(BaseModel):
    installed: bool
    path: str
    previous_version: str | None = None
    new_version: str | None = None
    version_bump_level: str | None = None
    version_bump_reason: str | None = None


class ValidateRequest(BaseModel):
    manifest: SkillManifest
    files: list[GeneratedFile] | None = Field(
        default=None,
        description="Optional generated files to validate alongside the manifest.",
    )


class ValidationIssue(BaseModel):
    severity: str = "error"  # error | warning
    code: str
    message: str


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
