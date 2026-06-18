"""Eval runner — run a skill against prompts and score responses.

For each prompt:
  1. Call the active AI provider with the skill's SKILL.md as the system prompt
     and the test prompt as the user message → produces a response.
  2. Call the provider again (LLM-as-judge) to score that response against the
     skill's own output_standards + a fixed rubric → {score: 0–10, reasoning}.
  3. Persist an EvalResult.

The mock provider returns deterministic responses + scores, so evals work
offline just like planning. A cost guard caps the number of (skill × prompt)
calls per run.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ...database import EvalResultRecord, EvalRunRecord, session_scope
from ...settings import get_settings
from ..ai_provider import AIProvider, AIProviderError, get_active_provider
from ..skill_registry import SkillRegistry

log = logging.getLogger(__name__)

# Hard cap on (skill × prompt) completions per run, *2 for the judge calls.
DEFAULT_MAX_CALLS = 50


@dataclass
class EvalRunSummary:
    run_id: int
    skill_name: str
    suite_name: str
    aggregate_score: float | None
    results: list[dict[str, Any]] = field(default_factory=list)


# ---- judge prompt ----

JUDGE_SYSTEM = """You are an impartial evaluator of an AI assistant's response, given a specific skill definition and a user prompt.

Score the response from 0 to 10 based on this rubric:
- Adherence to the skill's output standards (the skill lists what good output looks like).
- Whether it references the right tools/frameworks for this skill's domain.
- Whether it follows the skill's workflow and best practices.
- Whether it is concrete and specific (not generic advice), and actionable.

Penalize: generic "full-stack" advice that ignores the skill's specific stack,
vagueness, missing the skill's required tools, or ignoring the skill's workflow.

Return ONLY a JSON object: {"score": <0-10>, "reasoning": "<one or two sentences>"}.
No prose, no code fences."""


class EvalRunner:
    """Run a skill against prompts and score the responses."""

    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider or get_active_provider()

    def run(
        self,
        *,
        skill_name: str,
        prompts: list[str],
        suite_name: str = "",
        suite_id: int | None = None,
    ) -> EvalRunSummary:
        """Run *skill_name* against *prompts*, scoring each. Returns a summary."""
        skill_md, manifest = self._load_skill(skill_name)
        output_standards = (manifest.get("output_standards") or []) if manifest else []
        skill_version = (manifest.get("skill", {}) or {}).get("version", "")

        # Cost guard.
        max_calls = int(getattr(get_settings(), "eval_max_calls", DEFAULT_MAX_CALLS))
        prompts = [p for p in prompts if p and p.strip()]
        if len(prompts) > max_calls:
            prompts = prompts[:max_calls]
            log.warning("eval run truncated to %d prompts (cost guard)", max_calls)

        # Create the run row first.
        run = self._create_run(skill_name, skill_version, suite_name, suite_id)

        results: list[dict[str, Any]] = []
        scores: list[float] = []
        for prompt in prompts:
            result = self._eval_one(skill_md, prompt, output_standards, skill_name)
            result["run_id"] = run.id
            self._save_result(run.id, result)
            results.append(result)
            if result["status"] == "ok" and result.get("score") is not None:
                scores.append(float(result["score"]))

        aggregate = round(sum(scores) / len(scores), 2) if scores else None
        self._finalize_run(run.id, aggregate)

        return EvalRunSummary(
            run_id=run.id,
            skill_name=skill_name,
            suite_name=suite_name,
            aggregate_score=aggregate,
            results=results,
        )

    # ---- per-prompt ----
    def _eval_one(
        self,
        skill_md: str,
        prompt: str,
        output_standards: list[str],
        skill_name: str,
    ) -> dict[str, Any]:
        if self._provider.name == "mock":
            return self._mock_response(prompt, skill_name)

        # Truncate the skill definition we send as system context. Slow
        # providers (e.g. Z.ai/GLM) time out when handed the full SKILL.md
        # (often several KB); the eval needs the skill's identity, workflow,
        # and output standards — not every scaffold — so we keep the head.
        system_for_call = self._truncate_context(skill_md)

        try:
            response = self._provider.complete(system=system_for_call, user=prompt)
        except AIProviderError as exc:
            return {"prompt": prompt, "response": "", "score": None, "reasoning": str(exc), "status": "error"}

        try:
            judged = self._provider.complete_json(
                system=JUDGE_SYSTEM,
                user=self._judge_user(prompt, response, output_standards),
            )
            score = self._extract_score(judged)
            reasoning = str(judged.get("reasoning", "")) if isinstance(judged, dict) else ""
        except AIProviderError as exc:
            return {
                "prompt": prompt,
                "response": response,
                "score": None,
                "reasoning": f"judge failed: {exc}",
                "status": "error",
            }

        return {
            "prompt": prompt,
            "response": response,
            "score": score,
            "reasoning": reasoning,
            "status": "ok",
        }

    def _judge_user(self, prompt: str, response: str, standards: list[str]) -> str:
        return (
            f"Skill output standards:\n{json.dumps(standards)}\n\n"
            f"User prompt:\n{prompt}\n\n"
            f"Assistant response to evaluate:\n{response}\n\n"
            "Score this response 0–10 as JSON."
        )

    def _truncate_context(self, skill_md: str) -> str:
        """Keep the head of SKILL.md under ``eval_context_max_chars``.

        The generate call only needs the skill's identity, workflow, and output
        standards — not every scaffolded template. Trimming the context cuts
        tokens and keeps slow providers (Z.ai/GLM, large Ollama models) inside
        the read timeout.
        """
        max_chars = int(getattr(get_settings(), "eval_context_max_chars", 4000))
        if max_chars <= 0 or len(skill_md) <= max_chars:
            return skill_md
        truncated = skill_md[:max_chars].rsplit("\n", 1)[0]  # don't break a line
        return truncated + "\n\n[... skill definition truncated for evaluation ...]"

    def _extract_score(self, judged: Any) -> float | None:
        if isinstance(judged, dict):
            s = judged.get("score")
            try:
                v = float(s)
                return max(0.0, min(10.0, v))
            except (TypeError, ValueError):
                return None
        return None

    # ---- mock path (offline) ----
    def _mock_response(self, prompt: str, skill_name: str) -> dict[str, Any]:
        # Deterministic, plausible response + score. The score varies a little
        # with the prompt so runs aren't all identical.
        resp = (
            f"[mock] Following the {skill_name} skill workflow for: {prompt[:80]}…\n"
            "Recommended tools are applied; output standards are met."
        )
        # Stable-ish score in [5, 9] derived from the prompt length.
        base = 5.0 + (len(prompt) % 5)
        return {
            "prompt": prompt,
            "response": resp,
            "score": float(base),
            "reasoning": "mock judge: response references the skill's tools and workflow.",
            "status": "ok",
        }

    # ---- skill loading ----
    def _load_skill(self, skill_name: str) -> tuple[str, dict[str, Any]]:
        """Return (SKILL.md content, parsed config.yaml) for an installed skill."""
        record = SkillRegistry().get(skill_name)
        if record is None:
            raise ValueError(f"No installed skill named {skill_name!r}")
        skill_dir = Path(record.path)
        skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8") if (skill_dir / "SKILL.md").is_file() else ""
        manifest: dict[str, Any] = {}
        cfg = skill_dir / "config.yaml"
        if cfg.is_file():
            try:
                manifest = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                manifest = {}
        return skill_md, manifest

    # ---- persistence ----
    def _create_run(self, skill_name: str, version: str, suite_name: str, suite_id: int | None) -> EvalRunRecord:
        provider_name = self._provider.name
        model = self._resolve_model_label()
        with session_scope() as session:
            row = EvalRunRecord(
                suite_id=suite_id,
                suite_name=suite_name,
                skill_name=skill_name,
                skill_version=version,
                provider=provider_name,
                model=model,
            )
            session.add(row)
            session.flush()
            return EvalRunRecord(**row.model_dump())

    def _finalize_run(self, run_id: int, aggregate: float | None) -> None:
        with session_scope() as session:
            from sqlmodel import select

            row = session.exec(select(EvalRunRecord).where(EvalRunRecord.id == run_id)).first()
            if row:
                row.aggregate_score = aggregate
                session.add(row)

    def _save_result(self, run_id: int, result: dict[str, Any]) -> None:
        with session_scope() as session:
            row = EvalResultRecord(
                run_id=run_id,
                prompt=result.get("prompt", ""),
                response=result.get("response", ""),
                score=result.get("score"),
                reasoning=result.get("reasoning", ""),
                status=result.get("status", "ok"),
            )
            session.add(row)
            session.flush()
            result["id"] = row.id

    def _resolve_model_label(self) -> str:
        try:
            from ..user_config import get_user_config_store

            cfg = get_user_config_store().get_provider()
            return cfg.model or self._provider.name
        except Exception:
            return self._provider.name
