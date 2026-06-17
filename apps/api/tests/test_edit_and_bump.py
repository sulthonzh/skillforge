"""Integration tests: load installed skill → edit → re-install with auto-bump."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app
from skillforge_api.schemas.manifest import Tool
from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_installer import SkillInstaller


@pytest.fixture
def client():
    return TestClient(create_app())


def _plan_and_install(message: str):
    manifest, _ = AISkillPlanner().plan(message)
    outcome = SkillInstaller().install(manifest)
    assert outcome.installed
    return manifest, outcome


def test_reinstall_with_text_edit_bumps_patch():
    manifest, _ = _plan_and_install("backend skill for FastAPI and PostgreSQL")
    # Simulate a text-only edit.
    edited = manifest.model_copy(
        update={"skill": manifest.skill.model_copy(update={"description": "improved description"})}
    )
    outcome = SkillInstaller().install(edited, overwrite=True)
    assert outcome.installed
    assert outcome.version_bump is not None
    assert outcome.version_bump.level == "patch"
    assert outcome.previous_version == "0.1.0"
    assert outcome.new_version == "0.1.1"


def test_reinstall_with_tool_added_bumps_minor():
    manifest, _ = _plan_and_install("backend skill for FastAPI and PostgreSQL")
    from skillforge_api.schemas.manifest import Tool

    edited = manifest.model_copy(
        update={"tools": [*manifest.tools, Tool(name="Redis", category="databases", enabled=True, reason="caching")]}
    )
    outcome = SkillInstaller().install(edited, overwrite=True)
    assert outcome.version_bump.level == "minor"
    assert outcome.new_version == "0.2.0"


def test_reinstall_with_name_change_bumps_major():
    manifest, _ = _plan_and_install("backend skill for FastAPI and PostgreSQL")
    edited = manifest.model_copy(
        update={"skill": manifest.skill.model_copy(update={"name": "backend-fastapi-postgres-v2"})}
    )
    # Name change → new dir; the old one isn't overwritten, so this is a fresh
    # install with no bump (no previous version to compare). Verify the bump
    # logic directly via _compute_bump instead by keeping the name and checking
    # classification.
    from skillforge_api.services.versioning import classify_change

    b = classify_change(
        old_name="backend-fastapi-postgresql",
        new_name="backend-fastapi-postgres-v2",
        old_domain="Backend Engineering",
        new_domain="Backend Engineering",
        old_tool_names=[t.name for t in manifest.tools],
        new_tool_names=[t.name for t in manifest.tools],
        text_changed=False,
    )
    assert b.level == "major"


def test_bumped_version_persists_to_config_yaml():
    manifest, _ = _plan_and_install("backend skill for FastAPI and PostgreSQL")
    from skillforge_api.schemas.manifest import Tool
    import yaml
    from skillforge_api.settings import get_settings

    edited = manifest.model_copy(
        update={"tools": [*manifest.tools, Tool(name="Redis", category="databases", enabled=True, reason="caching")]}
    )
    SkillInstaller().install(edited, overwrite=True)
    cfg_path = get_settings().skills_dir / edited.skill.name / "config.yaml"
    persisted = yaml.safe_load(cfg_path.read_text())
    assert persisted["skill"]["version"] == "0.2.0"


def test_load_installed_manifest_endpoint(client):
    manifest, _ = _plan_and_install("backend skill for FastAPI and PostgreSQL")
    r = client.get(f"/api/registry/skills/{manifest.skill.name}/manifest")
    assert r.status_code == 200
    loaded = r.json()
    assert loaded["skill"]["name"] == manifest.skill.name
    assert len(loaded["tools"]) == len(manifest.tools)
    # The loaded manifest is editable (has all sections).
    assert loaded["workflow"]


def test_load_manifest_404_for_missing(client):
    r = client.get("/api/registry/skills/does-not-exist/manifest")
    assert r.status_code == 404


def test_install_response_carries_bump_info(client):
    manifest, _ = _plan_and_install("backend skill for FastAPI and PostgreSQL")
    # Add a tool and re-install via the API with overwrite. Serialize via
    # mode="json" so datetimes become strings the TestClient can transport.
    edited = manifest.model_copy(
        update={"tools": [*manifest.tools, Tool(name="Redis", category="databases", enabled=True, reason="caching")]}
    )
    body = {"manifest": edited.model_dump(mode="json"), "overwrite": True}
    r = client.post("/api/skills/install", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["installed"] is True
    assert data["version_bump_level"] == "minor"
    assert data["previous_version"] == "0.1.0"
    assert data["new_version"] == "0.2.0"
