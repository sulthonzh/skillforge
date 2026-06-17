"""Chat / skill-planning router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..schemas.chat import ChatPlanRequest, ChatPlanResponse
from ..schemas.manifest import SkillManifest, Tool
from ..services.ai_provider import AIProviderError
from ..services.ai_skill_planner import AISkillPlanner

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/plan-skill", response_model=ChatPlanResponse)
async def plan_skill_endpoint(req: ChatPlanRequest) -> ChatPlanResponse:
    """Plan a skill manifest from a natural-language message."""
    try:
        planner = AISkillPlanner()
        manifest, explanation = planner.plan(req.message)
    except AIProviderError as exc:
        log.warning("AI provider error during planning: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatPlanResponse(manifest=manifest, explanation=explanation)


class SuggestToolsRequest(BaseModel):
    manifest: SkillManifest
    hint: str = Field(default="", description="What the user wants to change or add.")
    category: str | None = Field(default=None, description="Restrict suggestions to a category.")


class SuggestToolsResponse(BaseModel):
    suggestions: list[Tool]


@router.post("/suggest-tools", response_model=SuggestToolsResponse)
async def suggest_tools_endpoint(req: SuggestToolsRequest) -> SuggestToolsResponse:
    """Suggest alternative/additional tools for the current manifest."""
    try:
        planner = AISkillPlanner()
        suggestions = planner.suggest_tools(req.manifest, hint=req.hint, category=req.category)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc
    return SuggestToolsResponse(suggestions=suggestions)
