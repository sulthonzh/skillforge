"""Tests for the skill-tools system: registry, script content, executor safety."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app
from skillforge_api.schemas.manifest import SkillManifest, SkillMeta, Tool
from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_generator import SkillGenerator
from skillforge_api.services.skill_installer import SkillInstaller
from skillforge_api.services.skill_tools.executor import (
    ExecutorError,
    ToolExecutor,
)
from skillforge_api.services.skill_tools.registry import get_registry
from skillforge_api.services.skill_tools.scripts import SCRIPTS


@pytest.fixture
def client():
    return TestClient(create_app())


def _plan(msg="backend skill for FastAPI, PostgreSQL, SQLAlchemy, Pytest, Docker"):
    return AISkillPlanner().plan(msg)[0]


# ---- Registry ----


def test_registry_returns_artifacts_for_known_tools():
    manifest = _plan()
    artifacts = get_registry().artifacts_for(manifest)
    assert len(artifacts) > 0
    # FastAPI skill → has dev_server.py.
    paths = {a.path for a in artifacts}
    assert "tools/dev_server.py" in paths


def test_registry_no_artifacts_for_unknown_tools():
    from skillforge_api.schemas.manifest import Architecture, Outputs, Safety, SkillAI

    manifest = SkillManifest(
        skill=SkillMeta(name="x-y-z", title="X", domain="Backend", description="x", version="0.1.0"),
        ai=SkillAI(),
        tools=[Tool(name="SomeUnknownTool", category="misc")],
        architecture=Architecture(),
        outputs=Outputs(),
        safety=Safety(),
    )
    assert get_registry().artifacts_for(manifest) == []


def test_registry_dedupes_artifacts():
    # FastAPI + Docker both might reference Dockerfile; should appear once.
    manifest = _plan("backend skill for FastAPI and Docker")
    paths = [a.path for a in get_registry().artifacts_for(manifest)]
    assert paths.count("Dockerfile") == 1


def test_registry_cli_targets_and_map():
    manifest = _plan()
    reg = get_registry()
    targets = reg.cli_targets(manifest)
    assert "dev" in targets or "test" in targets  # at least one CLI command
    cmd_map = reg.cli_command_map(manifest)
    assert ":" in cmd_map  # has entries


# ---- Script content (real, not stubs) ----


def test_scripts_are_real_not_stubs():
    """Generated scripts should be runnable, not contain 'TODO' or 'pass'."""
    dev = SCRIPTS["fastapi/dev_server.py"]
    assert "uvicorn.run" in dev  # actually launches uvicorn
    assert "import" in dev
    assert "TODO" not in dev

    migrate = SCRIPTS["alembic/migrate.sh"]
    assert "alembic upgrade head" in migrate  # actually runs alembic

    ci = SCRIPTS["cicd/ci.yml"]
    assert "pytest" in ci and "actions/checkout" in ci  # valid GH Actions workflow


def test_config_pyproject_has_dependencies():
    cfg = SCRIPTS["config/pyproject.toml"]
    assert "fastapi" in cfg
    assert "[project]" in cfg


def test_all_script_ids_exist_in_scripts_dict():
    """Every Artifact in the registry maps to a real SCRIPTS entry."""
    from skillforge_api.services.skill_tools.registry import _TOOL_ARTIFACTS

    missing = set()
    for artifacts in _TOOL_ARTIFACTS.values():
        for art in artifacts:
            if art.script_id not in SCRIPTS:
                missing.add(art.script_id)
    assert missing == set(), f"Missing scripts: {missing}"


# ---- Generator emits tools ----


def test_generator_emits_tools_dir():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    tools_files = [f.path for f in files if f.path.startswith("tools/")]
    assert "tools/dev_server.py" in tools_files
    assert "tools/cli.py" in tools_files
    assert "tools/Makefile" in tools_files
    assert "tools/mcp_server.py" in tools_files


def test_generator_emits_stack_configs():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    paths = {f.path for f in files}
    assert "config/pyproject.toml" in paths
    assert "config/requirements.txt" in paths
    assert "Dockerfile" in paths


def test_generated_makefile_has_targets():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    makefile = next(f.content for f in files if f.path == "tools/Makefile")
    assert ".PHONY" in makefile
    assert manifest.skill.name in makefile


# ---- Executor safety ----


def _install_skill():
    manifest = _plan()
    SkillInstaller().install(manifest, overwrite=True)
    return manifest.skill.name


def test_executor_preview_shows_command():
    name = _install_skill()
    executor = ToolExecutor()
    preview = executor.preview(name, "test.sh")
    assert preview.runnable is True
    assert "bash" in preview.command[0] or preview.command[0].endswith("python")
    assert "test.sh" in str(preview.command)


def test_executor_rejects_path_traversal():
    name = _install_skill()
    executor = ToolExecutor()
    with pytest.raises(ExecutorError):
        executor.preview(name, "../../../etc/passwd")


def test_executor_rejects_non_allowlisted_script():
    name = _install_skill()
    executor = ToolExecutor()
    # cli.py and Makefile and mcp_server.py are generated but not in the runnable allowlist
    # (Makefile isn't a script; mcp_server.py isn't in _RUNNABLE_SCRIPTS).
    preview = executor.preview(name, "mcp_server.py")
    assert preview.runnable is False


def test_executor_requires_confirm():
    name = _install_skill()
    executor = ToolExecutor()
    with pytest.raises(ExecutorError, match="confirmation"):
        executor.run(name, "test.sh", confirm=False)


def test_executor_unknown_skill():
    executor = ToolExecutor()
    with pytest.raises(ExecutorError):
        executor.preview("does-not-exist", "test.sh")


# ---- API endpoints ----


def test_list_tools_endpoint(client):
    name = _install_skill()
    r = client.get(f"/api/skills/{name}/tools")
    assert r.status_code == 200
    tools = r.json()
    assert len(tools) > 0
    assert any(t["script"] == "dev_server.py" for t in tools)


def test_preview_tool_endpoint(client):
    name = _install_skill()
    r = client.post(f"/api/skills/{name}/tools/test.sh/preview")
    assert r.status_code == 200
    assert r.json()["runnable"] is True


def test_run_tool_without_confirm_fails(client):
    name = _install_skill()
    r = client.post(f"/api/skills/{name}/tools/test.sh/run", json={"confirm": False})
    assert r.status_code == 400


def test_run_tool_path_traversal_rejected(client):
    name = _install_skill()
    # Path traversal in the URL is rejected by routing (404) or the executor (400).
    r = client.post(f"/api/skills/{name}/tools/..%2Fetc%2Fpasswd/preview")
    assert r.status_code in (400, 404, 422)
