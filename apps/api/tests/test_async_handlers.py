"""Tests that blocking provider calls don't block the event loop (Tier 0.1).

The proof: the blocking work runs on a WORKER thread, not the event-loop
thread. Before the threadpool wrap, run_eval / plan-skill ran their blocking
provider calls inline on the event loop, freezing every concurrent request.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_eval_run_offloads_to_worker_thread(client, monkeypatch):
    """EvalRunner.run must execute on a worker thread, not the event-loop thread.

    We record which thread run() executes on; it must differ from the main
    thread (the one TestClient drives the ASGI app on). If it's the same
    thread, the threadpool wrap is missing and the blocking eval would freeze
    the event loop.
    """
    from skillforge_api.services.bootstrap import bootstrap_skill_creator

    bootstrap_skill_creator()  # ensure the skill exists for the eval to find it

    import skillforge_api.services.eval.runner as runner_mod

    main_thread = threading.current_thread()
    run_thread: dict = {}

    real_run = runner_mod.EvalRunner.run

    def tracking_run(self, *args, **kwargs):
        run_thread["t"] = threading.current_thread()
        return real_run(self, *args, **kwargs)

    monkeypatch.setattr(runner_mod.EvalRunner, "run", tracking_run)

    r = client.post(
        "/api/eval/run",
        json={"skill_name": "skill-creator", "extra_prompts": ["prompt 1"]},
    )
    assert r.status_code == 200, r.text
    assert "t" in run_thread, "EvalRunner.run was never called"
    assert run_thread["t"] is not main_thread, (
        "EvalRunner.run ran on the main/event-loop thread — the threadpool wrap "
        "is missing, so blocking provider calls would freeze the event loop."
    )


def test_plan_skill_offloads_to_worker_thread(client, monkeypatch):
    """AISkillPlanner.plan must execute on a worker thread, not the event loop."""
    import skillforge_api.services.ai_skill_planner as planner_mod

    main_thread = threading.current_thread()
    plan_thread: dict = {}

    real_plan = planner_mod.AISkillPlanner.plan

    def tracking_plan(self, message):
        plan_thread["t"] = threading.current_thread()
        return real_plan(self, message)

    monkeypatch.setattr(planner_mod.AISkillPlanner, "plan", tracking_plan)

    r = client.post(
        "/api/chat/plan-skill",
        json={"message": "I need a backend skill for FastAPI and PostgreSQL"},
    )
    assert r.status_code == 200, r.text
    assert "t" in plan_thread, "AISkillPlanner.plan was never called"
    assert plan_thread["t"] is not main_thread, (
        "plan() ran on the main/event-loop thread — the threadpool wrap is missing."
    )


def test_suggest_tools_offloads_to_worker_thread(client, monkeypatch):
    """suggest_tools must execute on a worker thread."""
    import skillforge_api.services.ai_skill_planner as planner_mod

    main_thread = threading.current_thread()
    suggest_thread: dict = {}

    real_suggest = planner_mod.AISkillPlanner.suggest_tools

    def tracking_suggest(self, *args, **kwargs):
        suggest_thread["t"] = threading.current_thread()
        return real_suggest(self, *args, **kwargs)

    monkeypatch.setattr(planner_mod.AISkillPlanner, "suggest_tools", tracking_suggest)

    manifest = {
        "schema_version": "1.0",
        "skill": {
            "name": "backend-x-y", "title": "X Y", "domain": "Backend Engineering",
            "description": "backend api", "version": "0.1.0", "status": "draft",
        },
        "ai": {"generated_by": "skillforge", "planner_model": ""},
        "tools": [{"name": "Python", "category": "languages", "enabled": True, "reason": ""}],
        "architecture": {"patterns": []},
        "workflow": [], "best_practices": [], "output_standards": [],
        "outputs": {"required_files": ["SKILL.md"], "required_directories": ["prompts"]},
        "safety": {
            "auto_execute_scripts": False,
            "require_user_confirmation_before_install": True,
            "allow_network_access": False,
        },
    }
    r = client.post(
        "/api/chat/suggest-tools",
        json={"manifest": manifest, "hint": "add a database"},
    )
    assert r.status_code == 200, r.text
    assert "t" in suggest_thread, "suggest_tools was never called"
    assert suggest_thread["t"] is not main_thread, (
        "suggest_tools ran on the main/event-loop thread — threadpool wrap missing."
    )


def test_provider_test_offloads_to_worker_thread(client, monkeypatch):
    """test_provider_connection must execute on a worker thread."""
    import skillforge_api.routers.settings as settings_router

    main_thread = threading.current_thread()
    test_thread: dict = {}

    def tracking_test(cfg):
        test_thread["t"] = threading.current_thread()
        return {"ok": True, "detail": "mock", "models": ["mock-model"]}

    monkeypatch.setattr(settings_router, "test_provider_connection", tracking_test)

    client.put("/api/settings/provider", json={"provider": "mock"})
    r = client.post("/api/settings/provider/test", json={})
    assert r.status_code == 200
    assert "t" in test_thread, "test_provider_connection was never called"
    assert test_thread["t"] is not main_thread, (
        "test_provider_connection ran on the main thread — threadpool wrap missing."
    )
