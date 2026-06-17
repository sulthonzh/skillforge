"""Skill manifest schema.

The manifest is the single source of truth that drives generation, preview,
installation, and validation. The shape mirrors ``config.yaml`` but is also the
canonical JSON contract the AI planner returns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class SkillMeta(BaseModel):
    name: str = Field(..., description="kebab-case, specific skill name")
    title: str = ""
    domain: str = ""
    description: str = ""
    version: str = "0.1.0"
    status: str = "draft"


class SkillAI(BaseModel):
    generated_by: str = "skillforge"
    planner_model: str = ""
    created_at: datetime | None = None


class Tool(BaseModel):
    name: str
    category: str
    enabled: bool = True
    reason: str = ""


class Architecture(BaseModel):
    patterns: list[str] = Field(default_factory=list)


class Outputs(BaseModel):
    required_files: list[str] = Field(
        default_factory=lambda: ["SKILL.md", "README.md", "config.yaml"]
    )
    required_directories: list[str] = Field(
        default_factory=lambda: ["prompts", "templates", "scripts", "examples"]
    )


class Safety(BaseModel):
    auto_execute_scripts: bool = False
    require_user_confirmation_before_install: bool = True
    allow_network_access: bool = False


# Names that are too generic to ever be accepted.
GENERIC_NAMES = frozenset(
    {
        "fullstack",
        "full-stack",
        "backend",
        "frontend",
        "data",
        "devops",
        "general",
        "engineering",
        "skill",
        "default",
        "generic",
        "template",
        "api",
        "service",
        "app",
        "application",
    }
)


class SkillManifest(BaseModel):
    """The full editable skill manifest.

    Fields are tolerant (``extra='allow'``) so the Web UI can round-trip custom
    keys added by users. Validation is enforced in :mod:`skill_validator`, but a
    couple of cheap structural checks live here so bad input fails fast.
    """

    schema_version: str = "1.0"
    skill: SkillMeta
    ai: SkillAI = Field(default_factory=SkillAI)
    tools: list[Tool] = Field(default_factory=list)
    architecture: Architecture = Field(default_factory=Architecture)
    workflow: list[str] = Field(default_factory=list)
    best_practices: list[str] = Field(default_factory=list)
    output_standards: list[str] = Field(default_factory=list)
    outputs: Outputs = Field(default_factory=Outputs)
    safety: Safety = Field(default_factory=Safety)
    example_prompts: list[str] = Field(default_factory=list)
    example_outputs: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    @field_validator("skill")
    @classmethod
    def _strip_skill(cls, v: SkillMeta) -> SkillMeta:
        v.name = v.name.strip()
        v.title = v.title.strip() or v.name
        return v

    @property
    def name(self) -> str:
        return self.skill.name

    @property
    def enabled_tools(self) -> list[Tool]:
        return [t for t in self.tools if t.enabled]

    @model_validator(mode="after")
    def _ensure_default_lists(self) -> "SkillManifest":
        # Guarantee mutable defaults are non-None even when JSON omits them.
        return self
