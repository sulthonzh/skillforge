"""Registry schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InstalledSkill(BaseModel):
    name: str
    title: str = ""
    domain: str = ""
    path: str
    version: str = "0.1.0"
    installed_at: datetime | None = None


class RegistryListResponse(BaseModel):
    skills: list[InstalledSkill] = Field(default_factory=list)


class RegistryMutationResponse(BaseModel):
    removed: bool = False
    installed: bool = False
    name: str | None = None
    path: str | None = None
