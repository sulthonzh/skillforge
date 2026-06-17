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
    assert set(r.json()["providers"]) == {"mock", "openai-compatible", "ollama-local"}


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
