"""Tests for the settings router, suggest-tools, and bootstrap features."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app
from skillforge_api.services import user_config
from skillforge_api.services.bootstrap import bootstrap_skill_creator


@pytest.fixture
def client():
    return TestClient(create_app())


# ---- settings router ----


def test_list_providers(client):
    r = client.get("/api/settings/providers")
    assert r.status_code == 200
    assert set(r.json()["providers"]) == {
        "mock", "openai-compatible", "ollama-local", "anthropic", "gemini", "cohere"
    }


def test_list_presets(client):
    r = client.get("/api/settings/presets")
    assert r.status_code == 200
    presets = r.json()["presets"]
    assert len(presets) >= 5
    keys = {p["key"] for p in presets}
    assert {"openai", "groq", "mistral", "deepseek"} <= keys
    # Each preset has the fields the UI needs.
    for p in presets:
        assert p["base_url"] and p["default_model"] and p["label"]


def test_get_provider_returns_masked(client):
    r = client.get("/api/settings/provider")
    assert r.status_code == 200
    body = r.json()
    assert "openai_api_key" not in body  # raw key never exposed
    assert "openai_api_key_preview" in body
    assert "provider" in body


def test_put_then_get_persists(client, tmp_path, monkeypatch):
    # Point the store at a temp file so we can observe persistence.
    monkeypatch.setattr(
        user_config, "get_user_config_store", lambda: user_config.UserConfigStore(tmp_path / "c.json")
    )
    r = client.put(
        "/api/settings/provider",
        json={"provider": "ollama-local", "model": "llama3.1", "ollama_base_url": "http://localhost:11434"},
    )
    assert r.status_code == 200
    assert r.json()["saved"] is True
    assert r.json()["provider"]["model"] == "llama3.1"

    r2 = client.get("/api/settings/provider")
    assert r2.json()["provider"] == "ollama-local"
    assert r2.json()["model"] == "llama3.1"


def test_put_rejects_unknown_provider(client):
    r = client.put("/api/settings/provider", json={"provider": "bogus"})
    assert r.status_code == 400


def test_test_connection_mock_always_ok(client):
    # Ensure mock is active.
    client.put("/api/settings/provider", json={"provider": "mock"})
    r = client.post("/api/settings/provider/test", json={})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_list_models_mock(client):
    client.put("/api/settings/provider", json={"provider": "mock"})
    r = client.get("/api/settings/models")
    assert r.status_code == 200
    assert r.json()["models"] == ["mock-model"]


# ---- suggest-tools ----


def _minimal_manifest():
    return {
        "schema_version": "1.0",
        "skill": {
            "name": "backend-x-y",
            "title": "X Y",
            "domain": "Backend Engineering",
            "description": "backend api",
            "version": "0.1.0",
            "status": "draft",
        },
        "ai": {"generated_by": "skillforge", "planner_model": ""},
        "tools": [{"name": "Python", "category": "languages", "enabled": True, "reason": ""}],
        "architecture": {"patterns": []},
        "workflow": [],
        "best_practices": [],
        "output_standards": [],
        "outputs": {"required_files": ["SKILL.md"], "required_directories": ["prompts"]},
        "safety": {
            "auto_execute_scripts": False,
            "require_user_confirmation_before_install": True,
            "allow_network_access": False,
        },
    }


def test_suggest_tools_returns_new_tools(client):
    r = client.post(
        "/api/chat/suggest-tools",
        json={"manifest": _minimal_manifest(), "hint": "add a database like PostgreSQL"},
    )
    assert r.status_code == 200
    suggestions = r.json()["suggestions"]
    assert len(suggestions) > 0
    # Suggested tools must not duplicate what's already in the manifest.
    names = {s["name"].lower() for s in suggestions}
    assert "python" not in names
    # The hint mentions a database, so a DB-class tool should appear.
    assert any("database" in s["category"] for s in suggestions)


def test_suggest_tools_excludes_existing(client):
    manifest = _minimal_manifest()
    manifest["tools"] = [
        {"name": "Python", "category": "languages", "enabled": True, "reason": ""},
        {"name": "FastAPI", "category": "frameworks", "enabled": True, "reason": ""},
        {"name": "PostgreSQL", "category": "databases", "enabled": True, "reason": ""},
    ]
    r = client.post("/api/chat/suggest-tools", json={"manifest": manifest, "hint": "more backend tools"})
    names = {s["name"].lower() for s in r.json()["suggestions"]}
    assert "python" not in names
    assert "fastapi" not in names
    assert "postgresql" not in names


# ---- bootstrap skill-creator ----


def test_bootstrap_installs_skill_creator():
    assert bootstrap_skill_creator() is True
    from skillforge_api.services.skill_registry import SkillRegistry

    names = [s.name for s in SkillRegistry().list_installed()]
    assert "skill-creator" in names


def test_bootstrap_is_idempotent():
    bootstrap_skill_creator()  # ensure present
    assert bootstrap_skill_creator() is False  # already there → no-op


def test_bootstrap_skill_is_valid():
    bootstrap_skill_creator()
    from skillforge_api.services.skill_validator import SkillValidator
    from skillforge_api.settings import get_settings

    path = get_settings().skills_dir / "skill-creator"
    result = SkillValidator().validate_directory(path)
    assert result.valid, [i.message for i in result.errors]


# ---------------------------------------------------------------------------
# Tier 0.2 — surface silent mock fallback (degradation signal)
# ---------------------------------------------------------------------------


def test_get_provider_reports_degraded_when_key_missing(client, tmp_path, monkeypatch):
    """When a real provider is configured but its key is missing, the API must
    report degraded=True + effective='mock' so the UI can warn the user.

    Regression for the silent-fallback bug: users picked e.g. Anthropic, left
    the key blank, and got mock output with no indication it wasn't real AI.
    """
    store = user_config.UserConfigStore(tmp_path / "c.json")
    store.set_provider({"provider": "anthropic", "model": "claude-3-5-sonnet-latest"})
    user_config.set_user_config_store(store)

    r = client.get("/api/settings/provider")
    body = r.json()
    assert body["provider"] == "anthropic"
    assert body["degraded"] is True
    assert body["effective"] == "mock"
    assert body["fallback_reason"]  # a non-empty message


def test_get_provider_reports_not_degraded_when_mock_chosen(client, tmp_path, monkeypatch):
    """When the user deliberately chose mock, that's not 'degraded' — it's what
    they asked for. provider == effective == mock, degraded=False."""
    store = user_config.UserConfigStore(tmp_path / "c.json")
    store.set_provider({"provider": "mock"})
    user_config.set_user_config_store(store)

    r = client.get("/api/settings/provider")
    body = r.json()
    assert body["provider"] == "mock"
    assert body["effective"] == "mock"
    assert body["degraded"] is False


def test_get_provider_reports_not_degraded_when_configured_ok(client, tmp_path, monkeypatch):
    """A fully-configured real provider reports degraded=False."""
    store = user_config.UserConfigStore(tmp_path / "c.json")
    store.set_provider(
        {"provider": "ollama-local", "model": "llama3.1", "ollama_base_url": "http://localhost:11434"}
    )
    user_config.set_user_config_store(store)

    r = client.get("/api/settings/provider")
    body = r.json()
    assert body["provider"] == "ollama-local"
    assert body["degraded"] is False
    assert body["effective"] == "ollama-local"


def test_get_provider_status_function():
    """get_provider_status() returns the degradation dict directly (unit-level)."""
    from skillforge_api.services.ai_provider import get_provider_status

    status = get_provider_status()
    assert "configured" in status
    assert "effective" in status
    assert "degraded" in status
    assert "fallback_reason" in status
    assert isinstance(status["degraded"], bool)


def test_planner_model_is_mock_on_mock_path():
    """The manifest's planner_model must be 'mock' (not the user's configured
    model) when the mock provider is active. Regression for item 1.6: the mock
    path stamped the user's real model name onto heuristic output."""
    from skillforge_api.services.ai_skill_planner import AISkillPlanner

    planner = AISkillPlanner()
    # The conftest forces mock, so this planner runs mock.
    assert planner._provider.name == "mock"
    assert planner._planner_model == "mock"
