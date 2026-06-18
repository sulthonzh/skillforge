"""Chat / skill-planning router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..schemas.chat import ChatPlanRequest, ChatPlanResponse
from ..schemas.manifest import SkillManifest, Tool
from ..services.ai_provider import AIProviderError
from ..services.ai_skill_planner import AISkillPlanner

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/plan-skill", response_model=ChatPlanResponse)
async def plan_skill_endpoint(req: ChatPlanRequest) -> ChatPlanResponse:
    """Plan a skill manifest from a natural-language message.

    The planner's provider.complete() is a blocking HTTP call, so we offload
    the whole plan() to a worker thread via run_in_threadpool — otherwise a
    slow LLM response would block the event loop and stall every concurrent
    request (health checks, marketplace, etc.). (Tier 0.1.)
    """
    try:
        planner = AISkillPlanner()
        manifest, explanation = await run_in_threadpool(planner.plan, req.message)
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
    """Suggest alternative/additional tools for the current manifest.

    Offloaded to a threadpool for the same reason as plan-skill (Tier 0.1).
    """
    try:
        planner = AISkillPlanner()
        suggestions = await run_in_threadpool(
            planner.suggest_tools, req.manifest, hint=req.hint, category=req.category
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"AI provider error: {exc}") from exc
    return SuggestToolsResponse(suggestions=suggestions)
