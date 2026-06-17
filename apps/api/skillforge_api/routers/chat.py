"""Chat / skill-planning router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..schemas.chat import ChatPlanRequest, ChatPlanResponse
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
