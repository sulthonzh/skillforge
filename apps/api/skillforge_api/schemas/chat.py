"""Chat / skill-planning request & response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .manifest import SkillManifest


class ChatPlanRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Natural-language engineering need.")


class ChatPlanResponse(BaseModel):
    manifest: SkillManifest
    explanation: str = Field(..., description="Human-readable summary of tool recommendations.")
