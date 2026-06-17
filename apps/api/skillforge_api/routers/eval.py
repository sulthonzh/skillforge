"""Eval harness router — run skills against test prompts and compare them."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import select

from ..database import EvalResultRecord, EvalRunRecord, session_scope
from ..services.eval.runner import EvalRunner
from ..services.eval.suites import EvalSuiteStore, SuiteNotFound, get_suite_store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/eval", tags=["eval"])


# ---- request/response models ----


class SuiteBody(BaseModel):
    name: str
    description: str = ""
    prompts: list[str] = Field(default_factory=list)


class RunBody(BaseModel):
    skill_name: str
    suite_name: str | None = None
    extra_prompts: list[str] = Field(default_factory=list)
    use_skill_examples: bool = True


class RunOverrideBody(BaseModel):
    """Manual override of a result's winner/score for human-in-the-loop compare."""

    score: float | None = None
    reasoning: str | None = None


# ---- suites ----


@router.get("/suites")
async def list_suites() -> dict:
    store = get_suite_store()
    # Seed the default suite if none exist yet (so the UI always has one).
    if not store.list_all():
        store.seed_default()
    return {"suites": store.list_all()}


@router.post("/suites")
async def upsert_suite(body: SuiteBody) -> dict:
    try:
        suite = get_suite_store().create(body.name, body.description, body.prompts)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"suite": suite}


@router.delete("/suites/{name}")
async def delete_suite(name: str) -> dict:
    removed = get_suite_store().delete(name)
    if not removed:
        raise HTTPException(404, f"No suite named {name!r}.")
    return {"removed": True, "name": name}


# ---- runs ----


def _resolve_prompts(body: RunBody) -> tuple[list[str], str, int | None]:
    """Return (prompts, suite_name, suite_id) for a run."""
    prompts: list[str] = []
    suite_name = ""
    suite_id: int | None = None

    if body.suite_name:
        try:
            suite = get_suite_store().get(body.suite_name)
        except SuiteNotFound as exc:
            raise HTTPException(404, f"No suite named {body.suite_name!r}.") from exc
        prompts.extend(suite["prompts"])
        suite_name = suite["name"]
        suite_id = suite.get("id")

    # Per-skill example prompts (apples-to-apples within a skill's own domain).
    if body.use_skill_examples:
        from ..services.skill_registry import SkillRegistry
        from pathlib import Path
        import yaml

        record = SkillRegistry().get(body.skill_name)
        if record:
            cfg = Path(record.path) / "config.yaml"
            if cfg.is_file():
                try:
                    manifest = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
                    prompts.extend(manifest.get("example_prompts") or [])
                except yaml.YAMLError:
                    pass

    # Dedup while preserving order.
    seen: set[str] = set()
    deduped = []
    for p in prompts + list(body.extra_prompts):
        key = p.strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped, suite_name, suite_id


@router.post("/run")
async def run_eval(body: RunBody) -> dict:
    """Run a skill against prompts and score the responses."""
    prompts, suite_name, suite_id = _resolve_prompts(body)
    if not prompts:
        raise HTTPException(400, "No prompts to evaluate. Pick a suite or add custom prompts.")
    try:
        runner = EvalRunner()
        summary = runner.run(
            skill_name=body.skill_name,
            prompts=prompts,
            suite_name=suite_name,
            suite_id=suite_id,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - provider errors
        log.warning("eval run failed: %s", exc)
        raise HTTPException(502, f"Eval run failed: {exc}") from exc

    return {
        "run_id": summary.run_id,
        "skill_name": summary.skill_name,
        "suite_name": summary.suite_name,
        "aggregate_score": summary.aggregate_score,
        "results": summary.results,
    }


@router.get("/runs")
async def list_runs(
    skill: str | None = Query(None),
    suite: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    with session_scope() as session:
        stmt = select(EvalRunRecord).order_by(EvalRunRecord.created_at.desc()).limit(limit)
        if skill:
            stmt = stmt.where(EvalRunRecord.skill_name == skill)
        if suite:
            stmt = stmt.where(EvalRunRecord.suite_name == suite)
        rows = session.exec(stmt).all()
        return {
            "runs": [
                {
                    "id": r.id,
                    "skill_name": r.skill_name,
                    "skill_version": r.skill_version,
                    "suite_name": r.suite_name,
                    "provider": r.provider,
                    "model": r.model,
                    "aggregate_score": r.aggregate_score,
                    "created_at": r.created_at,
                }
                for r in rows
            ]
        }


def _run_to_dict(run: EvalRunRecord, results: list[EvalResultRecord]) -> dict:
    return {
        "id": run.id,
        "skill_name": run.skill_name,
        "skill_version": run.skill_version,
        "suite_name": run.suite_name,
        "provider": run.provider,
        "model": run.model,
        "aggregate_score": run.aggregate_score,
        "created_at": run.created_at,
        "results": [
            {
                "id": r.id,
                "prompt": r.prompt,
                "response": r.response,
                "score": r.score,
                "reasoning": r.reasoning,
                "status": r.status,
            }
            for r in results
        ],
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: int) -> dict:
    with session_scope() as session:
        run = session.exec(select(EvalRunRecord).where(EvalRunRecord.id == run_id)).first()
        if not run:
            raise HTTPException(404, f"No run #{run_id}.")
        results = session.exec(
            select(EvalResultRecord).where(EvalResultRecord.run_id == run_id)
        ).all()
        return _run_to_dict(run, results)


@router.patch("/runs/{run_id}/results/{result_id}")
async def override_result(run_id: int, result_id: int, body: RunOverrideBody) -> dict:
    """Manually override a result's score/reasoning (human-in-the-loop)."""
    with session_scope() as session:
        row = session.exec(
            select(EvalResultRecord).where(EvalResultRecord.id == result_id, EvalResultRecord.run_id == run_id)
        ).first()
        if not row:
            raise HTTPException(404, f"No result #{result_id} in run #{run_id}.")
        if body.score is not None:
            row.score = max(0.0, min(10.0, float(body.score)))
        if body.reasoning is not None:
            row.reasoning = body.reasoning
        session.add(row)
        # Recompute the run's aggregate.
        all_results = session.exec(
            select(EvalResultRecord).where(EvalResultRecord.run_id == run_id)
        ).all()
        scored = [r.score for r in all_results if r.score is not None]
        run = session.exec(select(EvalRunRecord).where(EvalRunRecord.id == run_id)).first()
        if run:
            run.aggregate_score = round(sum(scored) / len(scored), 2) if scored else None
            session.add(run)
        return {
            "id": row.id,
            "score": row.score,
            "reasoning": row.reasoning,
            "aggregate_score": run.aggregate_score if run else None,
        }


@router.delete("/runs/{run_id}")
async def delete_run(run_id: int) -> dict:
    with session_scope() as session:
        run = session.exec(select(EvalRunRecord).where(EvalRunRecord.id == run_id)).first()
        if not run:
            raise HTTPException(404, f"No run #{run_id}.")
        results = session.exec(
            select(EvalResultRecord).where(EvalResultRecord.run_id == run_id)
        ).all()
        for r in results:
            session.delete(r)
        session.delete(run)
    return {"removed": True, "id": run_id}


# ---- compare ----


@router.get("/compare")
async def compare(
    skills: str = Query(..., description="Comma-separated skill names"),
    suite: str | None = Query(None),
) -> dict:
    """Side-by-side matrix: per prompt, each skill's latest-run response + score."""
    skill_names = [s.strip() for s in skills.split(",") if s.strip()]
    if len(skill_names) < 2:
        raise HTTPException(400, "Provide at least two skills to compare.")

    # Find each skill's most recent run (optionally within a suite).
    runs: dict[str, dict[str, Any]] = {}
    with session_scope() as session:
        for name in skill_names:
            stmt = select(EvalRunRecord).where(EvalRunRecord.skill_name == name).order_by(EvalRunRecord.created_at.desc())
            if suite:
                stmt = stmt.where(EvalRunRecord.suite_name == suite)
            run = session.exec(stmt.limit(1)).first()
            if not run:
                continue
            results = session.exec(
                select(EvalResultRecord).where(EvalResultRecord.run_id == run.id)
            ).all()
            runs[name] = _run_to_dict(run, results)

    # Build the per-prompt matrix keyed by prompt text.
    prompts: list[str] = []
    seen: set[str] = set()
    for run_data in runs.values():
        for r in run_data["results"]:
            p = r["prompt"]
            if p not in seen:
                seen.add(p)
                prompts.append(p)

    matrix: list[dict[str, Any]] = []
    for p in prompts:
        row: dict[str, Any] = {"prompt": p, "by_skill": {}}
        scores: list[float] = []
        for name, run_data in runs.items():
            match = next((r for r in run_data["results"] if r["prompt"] == p), None)
            if match:
                row["by_skill"][name] = match
                if match["score"] is not None:
                    scores.append(float(match["score"]))
        # Highlight the winner by score (ties = no winner).
        if scores:
            top = max(scores)
            winners = [
                name
                for name in skill_names
                if name in row["by_skill"]
                and row["by_skill"][name]["score"] is not None
                and float(row["by_skill"][name]["score"]) == top
            ]
            row["winner"] = winners[0] if len(winners) == 1 else None
            row["top_score"] = top
        matrix.append(row)

    summary = {
        name: {
            "aggregate_score": data["aggregate_score"],
            "suite_name": data["suite_name"],
            "run_id": data["id"],
            "created_at": data["created_at"],
        }
        for name, data in runs.items()
    }
    return {"skills": list(runs.keys()), "matrix": matrix, "summary": summary}
