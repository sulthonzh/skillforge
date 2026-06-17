"""Tests for the registry repository, registry service, and registry API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import app
from skillforge_api.repositories.registry_repository import RegistryRepository
from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_installer import SkillInstaller
from skillforge_api.services.skill_registry import SkillRegistry


def _plan():
    return AISkillPlanner().plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )[0]


# ---- repository ----


def test_repository_upsert_and_get():
    repo = RegistryRepository()
    repo.upsert(name="x-y-z", title="X Y Z", domain="Backend Engineering", version="0.1.0", path="/tmp/x-y-z")
    got = repo.get("x-y-z")
    assert got is not None
    assert got.title == "X Y Z"
    # Upsert updates existing.
    repo.upsert(name="x-y-z", title="Updated", domain="Backend Engineering", version="0.2.0", path="/tmp/x-y-z")
    assert repo.get("x-y-z").title == "Updated"
    assert repo.get("x-y-z").version == "0.2.0"


def test_repository_list_orders_by_name():
    repo = RegistryRepository()
    for n in ("c-c-c", "a-a-a", "b-b-b"):
        repo.upsert(name=n, title=n, domain="Backend", version="0.1.0", path=f"/tmp/{n}")
    names = [r.name for r in repo.list_all()]
    assert names == sorted(names)


def test_repository_delete():
    repo = RegistryRepository()
    repo.upsert(name="to-remove", title="x", domain="d", version="0.1.0", path="/tmp/x")
    assert repo.delete("to-remove") is True
    assert repo.delete("to-remove") is False


# ---- service ----


def test_registry_service_lists_and_removes():
    manifest = _plan()
    SkillInstaller().install(manifest)
    registry = SkillRegistry()
    listed = registry.list_installed()
    assert any(s.name == manifest.skill.name for s in listed)
    assert registry.get(manifest.skill.name).domain == manifest.skill.domain
    assert registry.remove(manifest.skill.name) is True
    assert registry.get(manifest.skill.name) is None


# ---- API ----


@pytest.fixture
def client():
    return TestClient(app)


def test_api_list_skills(client):
    manifest = _plan()
    SkillInstaller().install(manifest)
    r = client.get("/api/registry/skills")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["skills"]]
    assert manifest.skill.name in names


def test_api_get_skill_404(client):
    r = client.get("/api/registry/skills/does-not-exist")
    assert r.status_code == 404


def test_api_remove_skill(client):
    manifest = _plan()
    SkillInstaller().install(manifest)
    r = client.delete(f"/api/registry/skills/{manifest.skill.name}")
    assert r.status_code == 200
    assert r.json()["removed"] is True
    # Second removal is 404.
    r2 = client.delete(f"/api/registry/skills/{manifest.skill.name}")
    assert r2.status_code == 404
