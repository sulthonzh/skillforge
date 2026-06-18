"""Tests for the eval harness: suites, runner, persistence, compare, overrides."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app
from skillforge_api.services.bootstrap import bootstrap_skill_creator
from skillforge_api.services.eval.runner import EvalRunner
from skillforge_api.services.eval.suites import (
    DEFAULT_SUITE,
    EvalSuiteStore,
    SuiteNotFound,
)


@pytest.fixture
def client():
    return TestClient(create_app())


def _ensure_skill_installed():
    """The bootstrap skill-creator skill is the eval test subject."""
    bootstrap_skill_creator()


# ---- EvalSuiteStore ----


def test_seed_default_creates_general_suite(tmp_path):
    store = EvalSuiteStore(tmp_path)
    store.seed_default()
    suites = store.list_all()
    assert len(suites) == 1
    assert suites[0]["name"] == DEFAULT_SUITE["name"]
    assert len(suites[0]["prompts"]) == len(DEFAULT_SUITE["prompts"])
    # Idempotent.
    store.seed_default()
    assert len(store.list_all()) == 1


def test_seed_default_is_idempotent(tmp_path):
    store = EvalSuiteStore(tmp_path)
    store.seed_default()
    store.seed_default()
    assert len(store.list_all()) == 1


def test_create_and_get_suite(tmp_path):
    store = EvalSuiteStore(tmp_path)
    created = store.create("backend-basic", "Backend prompts", ["design an API", "pick an ORM"])
    assert created["name"] == "backend-basic"
    assert created["prompts"] == ["design an API", "pick an ORM"]
    got = store.get("backend-basic")
    assert got["prompts"] == ["design an API", "pick an ORM"]
    # JSON mirror exists.
    assert (tmp_path / "backend-basic.json").is_file()


def test_update_existing_suite(tmp_path):
    store = EvalSuiteStore(tmp_path)
    store.create("s", "old", ["a"])
    store.create("s", "new", ["a", "b"])
    got = store.get("s")
    assert got["description"] == "new"
    assert got["prompts"] == ["a", "b"]


def test_get_missing_suite_raises(tmp_path):
    store = EvalSuiteStore(tmp_path)
    with pytest.raises(SuiteNotFound):
        store.get("nope")


def test_delete_suite(tmp_path):
    store = EvalSuiteStore(tmp_path)
    store.create("s", "", ["a"])
    assert store.delete("s") is True
    assert store.delete("s") is False


# ---- EvalRunner (mock provider) ----


def test_runner_produces_scored_results():
    _ensure_skill_installed()
    runner = EvalRunner()
    summary = runner.run(
        skill_name="skill-creator",
        prompts=["What does this skill do?", "Outline its workflow."],
        suite_name="test",
    )
    assert summary.skill_name == "skill-creator"
    assert summary.run_id > 0
    assert len(summary.results) == 2
    for r in summary.results:
        assert r["status"] == "ok"
        assert r["score"] is not None
        assert 0.0 <= r["score"] <= 10.0
        assert r["response"]
    # Aggregate = mean of scores.
    expected = round(sum(r["score"] for r in summary.results) / 2, 2)
    assert summary.aggregate_score == expected


def test_runner_unknown_skill_raises():
    runner = EvalRunner()
    with pytest.raises(ValueError):
        runner.run(skill_name="does-not-exist", prompts=["x"])


def test_runner_cost_guard_truncates(monkeypatch):
    _ensure_skill_installed()
    from skillforge_api.settings import get_settings

    monkeypatch.setattr(get_settings(), "eval_max_calls", 2)
    runner = EvalRunner()
    summary = runner.run(
        skill_name="skill-creator",
        prompts=["a", "b", "c", "d", "e"],
        suite_name="guard",
    )
    assert len(summary.results) == 2  # truncated to max_calls


def test_runner_persists_run_and_results():
    _ensure_skill_installed()
    runner = EvalRunner()
    summary = runner.run(skill_name="skill-creator", prompts=["p1", "p2"], suite_name="persist")
    # Re-fetch the run via the DB.
    from sqlmodel import select

    from skillforge_api.database import EvalResultRecord, EvalRunRecord, session_scope

    with session_scope() as session:
        run = session.exec(select(EvalRunRecord).where(EvalRunRecord.id == summary.run_id)).first()
        assert run is not None
        assert run.aggregate_score == summary.aggregate_score
        results = session.exec(select(EvalResultRecord).where(EvalResultRecord.run_id == run.id)).all()
        assert len(results) == 2


# ---- router ----


def test_list_suites_seeds_default(client):
    r = client.get("/api/eval/suites")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["suites"]]
    assert "General" in names


def test_create_and_delete_suite_via_api(client):
    r = client.post("/api/eval/suites", json={"name": "api-suite", "description": "x", "prompts": ["one", "two"]})
    assert r.status_code == 200
    assert r.json()["suite"]["prompts"] == ["one", "two"]
    r2 = client.delete("/api/eval/suites/api-suite")
    assert r2.status_code == 200
    assert r2.json()["removed"] is True


def test_run_eval_endpoint(client):
    _ensure_skill_installed()
    r = client.post("/api/eval/run", json={
        "skill_name": "skill-creator",
        "extra_prompts": ["Explain this skill."],
        "use_skill_examples": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["skill_name"] == "skill-creator"
    assert len(body["results"]) == 1
    assert body["results"][0]["score"] is not None
    assert body["aggregate_score"] is not None


def test_run_eval_404_unknown_skill(client):
    r = client.post("/api/eval/run", json={"skill_name": "nope", "extra_prompts": ["x"], "use_skill_examples": False})
    assert r.status_code == 404


def test_list_runs(client):
    _ensure_skill_installed()
    client.post("/api/eval/run", json={"skill_name": "skill-creator", "extra_prompts": ["q"], "use_skill_examples": False})
    r = client.get("/api/eval/runs")
    assert r.status_code == 200
    assert len(r.json()["runs"]) >= 1


def test_get_run(client):
    _ensure_skill_installed()
    run = client.post("/api/eval/run", json={"skill_name": "skill-creator", "extra_prompts": ["q1"], "use_skill_examples": False}).json()
    r = client.get(f"/api/eval/runs/{run['run_id']}")
    assert r.status_code == 200
    assert r.json()["id"] == run["run_id"]
    assert len(r.json()["results"]) == 1


def test_override_result(client):
    _ensure_skill_installed()
    run = client.post("/api/eval/run", json={"skill_name": "skill-creator", "extra_prompts": ["q"], "use_skill_examples": False}).json()
    result_id = run["results"][0]["id"]
    r = client.patch(f"/api/eval/runs/{run['run_id']}/results/{result_id}", json={"score": 9.5, "reasoning": "human override"})
    assert r.status_code == 200
    assert r.json()["score"] == 9.5
    assert r.json()["aggregate_score"] == 9.5


def test_delete_run(client):
    _ensure_skill_installed()
    run = client.post("/api/eval/run", json={"skill_name": "skill-creator", "extra_prompts": ["q"], "use_skill_examples": False}).json()
    r = client.delete(f"/api/eval/runs/{run['run_id']}")
    assert r.status_code == 200
    assert r.json()["removed"] is True
    # Gone.
    assert client.get(f"/api/eval/runs/{run['run_id']}").status_code == 404


def test_compare_requires_two_skills(client):
    r = client.get("/api/eval/compare?skills=only-one")
    assert r.status_code == 400


def test_compare_matrix(client):
    _ensure_skill_installed()
    # Run skill-creator twice so compare has at least one run per "skill" name.
    # (Compare keys on skill_name, so we use the same skill twice — still valid
    # for testing the matrix shape.)
    client.post("/api/eval/run", json={"skill_name": "skill-creator", "extra_prompts": ["shared prompt"], "use_skill_examples": False})
    # compare needs 2 distinct skill names; install a second skill to compare.
    from skillforge_api.services.ai_skill_planner import AISkillPlanner
    from skillforge_api.services.skill_installer import SkillInstaller

    m, _ = AISkillPlanner().plan("backend skill for FastAPI and PostgreSQL")
    SkillInstaller().install(m)
    client.post("/api/eval/run", json={"skill_name": m.skill.name, "extra_prompts": ["shared prompt"], "use_skill_examples": False})

    r = client.get(f"/api/eval/compare?skills=skill-creator,{m.skill.name}")
    assert r.status_code == 200
    body = r.json()
    assert set(body["skills"]) == {"skill-creator", m.skill.name}
    assert len(body["matrix"]) >= 1
    row = body["matrix"][0]
    assert row["prompt"] == "shared prompt"
    assert set(row["by_skill"].keys()) == {"skill-creator", m.skill.name}


# ---------------------------------------------------------------------------
# Judge fallback — when the JSON judge returns empty/garbage, the eval must
# recover via a plain-text retry instead of marking a good response as failed.
# (Seen in the wild on Z.ai/GLM: json_mode produces an empty body.)
# ---------------------------------------------------------------------------


def test_judge_fallback_recovers_from_empty_json(monkeypatch):
    """When complete_json raises (empty/non-JSON judge response), the fallback
    judge retries with plain text and extracts the score via regex."""
    from skillforge_api.services.ai_provider import AIProvider
    from skillforge_api.services.eval.runner import EvalRunner

    class FlakyJudgeProvider(AIProvider):
        name = "flaky"

        def complete(self, system, user, *, json_mode=False, max_tokens=None):
            if json_mode:
                # Simulate Z.ai returning an empty body with json_mode set.
                return ""
            # Plain-text fallback: the model writes a score + justification.
            return "8\nThe response covers the key points well but misses an edge case."

    runner = EvalRunner(provider=FlakyJudgeProvider())
    result = runner._eval_one(
        skill_md="# Test skill\nA test skill.",
        prompt="How do I do X?",
        output_standards=["correct", "complete"],
        skill_name="test-skill",
    )
    # The fallback judge should have recovered the score.
    assert result["status"] == "ok", f"expected ok, got {result}"
    assert result["score"] == 8.0
    assert "fallback" in result["reasoning"].lower()


def test_judge_fallback_returns_error_when_both_fail(monkeypatch):
    """If both the JSON judge AND the text fallback fail, mark as error."""
    from skillforge_api.services.ai_provider import AIProvider, AIProviderError
    from skillforge_api.services.eval.runner import EvalRunner

    class BrokenProvider(AIProvider):
        name = "broken"

        def complete(self, system, user, *, json_mode=False, max_tokens=None):
            # Generate works, but the judge (both JSON and text) raises.
            if "Score this response" in user or "score" in system.lower():
                raise AIProviderError("provider is down")
            return "A valid generated response."

    runner = EvalRunner(provider=BrokenProvider())
    result = runner._eval_one(
        skill_md="# Test skill",
        prompt="How do I do X?",
        output_standards=["correct"],
        skill_name="test-skill",
    )
    assert result["status"] == "error"
    assert result["score"] is None
    # The response was still captured (generation succeeded).
    assert result["response"] == "A valid generated response."


def test_judge_fallback_extracts_score_from_text():
    """The regex extractor pulls the first 0-10 number from the text response."""
    from skillforge_api.services.ai_provider import AIProvider, AIProviderError
    from skillforge_api.services.eval.runner import EvalRunner

    class TextProvider(AIProvider):
        name = "text"

        def complete(self, system, user, *, json_mode=False, max_tokens=None):
            if json_mode:
                raise AIProviderError("not valid JSON")
            return "10\nPerfect answer."

    runner = EvalRunner(provider=TextProvider())
    score, reasoning = runner._judge_fallback(
        prompt="test", response="a response", standards=["x"],
        original_error=AIProviderError("json failed"),
    )
    assert score == 10.0
    assert "10" in reasoning or "Perfect" in reasoning
