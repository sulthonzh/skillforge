"""Tests for the symlink-deploy system: detector, symlink, undeploy."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app
from skillforge_api.services.bootstrap import bootstrap_skill_creator
from skillforge_api.services.symlink_deploy import (
    SymlinkDeployer,
    ToolTargetDetector,
)


@pytest.fixture
def client():
    return TestClient(create_app())


def _ensure_skill():
    bootstrap_skill_creator()


# ---- ToolTargetDetector ----


def test_detector_returns_known_tools():
    detector = ToolTargetDetector()
    targets = detector.detect()
    keys = {t.key for t in targets}
    assert {"claude-code", "zcode", "codex"} <= keys


def test_detector_marks_installed():
    detector = ToolTargetDetector()
    targets = detector.detect()
    # ZCode should be installed (we're running inside it).
    zcode = next(t for t in targets if t.key == "zcode")
    assert zcode.installed is True


def test_installed_targets_filtered():
    detector = ToolTargetDetector()
    installed = detector.installed_targets()
    assert all(t.installed for t in installed)


# ---- SymlinkDeployer (with temp home) ----


def test_deploy_creates_symlink(tmp_path, monkeypatch):
    # Point HOME at a temp dir so we don't touch real tool dirs.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    # Create a fake tool skills dir.
    tool_dir = fake_home / ".claude" / "skills"
    tool_dir.mkdir(parents=True)

    # Create a fake skill source.
    skill_src = tmp_path / "my-skill"
    skill_src.mkdir()
    (skill_src / "SKILL.md").write_text("# My Skill")

    deployer = SymlinkDeployer(ToolTargetDetector())
    result = deployer.deploy(skill_src, "my-skill", target_key="claude-code")

    assert len(result["deployments"]) == 1
    dep = result["deployments"][0]
    assert dep["status"] == "deployed"
    link = Path(dep["path"])
    assert link.is_symlink()
    assert link.resolve() == skill_src.resolve()


def test_deploy_to_all_installed(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    # Install two tools.
    (fake_home / ".claude" / "skills").mkdir(parents=True)
    (fake_home / ".zcode" / "skills").mkdir(parents=True)

    skill_src = tmp_path / "skill"
    skill_src.mkdir()
    (skill_src / "SKILL.md").write_text("# Skill")

    deployer = SymlinkDeployer(ToolTargetDetector())
    result = deployer.deploy(skill_src, "skill", target_key=None)

    deployed = [d for d in result["deployments"] if d["status"] == "deployed"]
    assert len(deployed) == 2


def test_deploy_copy_method(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    (fake_home / ".claude" / "skills").mkdir(parents=True)

    skill_src = tmp_path / "skill"
    skill_src.mkdir()
    (skill_src / "SKILL.md").write_text("# Skill")

    deployer = SymlinkDeployer(ToolTargetDetector())
    result = deployer.deploy(skill_src, "skill", target_key="claude-code", method="copy")

    dep = result["deployments"][0]
    assert dep["method"] == "copy"
    link = Path(dep["path"])
    assert not link.is_symlink()  # it's a copy, not a symlink
    assert link.is_dir()
    assert (link / "SKILL.md").read_text() == "# Skill"


def test_deploy_is_idempotent(tmp_path, monkeypatch):
    """Re-deploying over an existing symlink refreshes it without error."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    (fake_home / ".claude" / "skills").mkdir(parents=True)

    skill_src = tmp_path / "skill"
    skill_src.mkdir()
    (skill_src / "SKILL.md").write_text("# v1")

    deployer = SymlinkDeployer(ToolTargetDetector())
    deployer.deploy(skill_src, "skill", target_key="claude-code")

    # Update source + redeploy.
    (skill_src / "SKILL.md").write_text("# v2")
    deployer.deploy(skill_src, "skill", target_key="claude-code")

    link = fake_home / ".claude" / "skills" / "skill"
    assert (link / "SKILL.md").read_text() == "# v2"  # symlink → sees update


def test_undeploy_removes_symlink(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    (fake_home / ".claude" / "skills").mkdir(parents=True)

    skill_src = tmp_path / "skill"
    skill_src.mkdir()
    (skill_src / "SKILL.md").write_text("# Skill")

    deployer = SymlinkDeployer(ToolTargetDetector())
    deployer.deploy(skill_src, "skill", target_key="claude-code")
    assert (fake_home / ".claude" / "skills" / "skill").exists()

    result = deployer.undeploy("skill", target_key="claude-code")
    assert result["removals"][0]["status"] == "removed"
    assert not (fake_home / ".claude" / "skills" / "skill").exists()


def test_status_reports_deployed_targets(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    (fake_home / ".claude" / "skills").mkdir(parents=True)

    skill_src = tmp_path / "skill"
    skill_src.mkdir()
    (skill_src / "SKILL.md").write_text("# Skill")

    deployer = SymlinkDeployer(ToolTargetDetector())
    deployer.deploy(skill_src, "skill", target_key="claude-code")

    status = deployer.status("skill")
    claude = next(s for s in status if s["target"] == "claude-code")
    assert claude["deployed"] is True
    assert claude["method"] == "symlink"


# ---- API endpoints ----


def test_list_targets_endpoint(client):
    r = client.get("/api/deploy/targets")
    assert r.status_code == 200
    keys = {t["key"] for t in r.json()["targets"]}
    assert "claude-code" in keys


def test_deploy_status_endpoint(client):
    _ensure_skill()
    r = client.get("/api/deploy/skill-creator/status")
    assert r.status_code == 200
    assert r.json()["skill_name"] == "skill-creator"
    assert isinstance(r.json()["targets"], list)


def test_deploy_and_undeploy_endpoint(client):
    _ensure_skill()
    # Deploy to zcode (which is installed).
    r = client.post("/api/deploy/symlink", json={"skill_name": "skill-creator", "target_key": "zcode"})
    assert r.status_code == 200
    [d for d in r.json()["deployments"] if d["status"] == "deployed"]
    # Cleanup.
    client.post("/api/deploy/undeploy", json={"skill_name": "skill-creator", "target_key": "zcode"})


def test_deploy_unknown_skill(client):
    r = client.post("/api/deploy/symlink", json={"skill_name": "nope"})
    assert r.status_code == 404
