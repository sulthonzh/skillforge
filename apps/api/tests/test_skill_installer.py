"""Tests for the skill installer."""

from __future__ import annotations

import pytest

from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_installer import InstallerError, SkillInstaller
from skillforge_api.services.skill_registry import SkillRegistry
from skillforge_api.settings import get_settings


def _plan():
    return AISkillPlanner().plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )[0]


def test_install_writes_files_and_registers():
    manifest = _plan()
    installer = SkillInstaller()
    outcome = installer.install(manifest)
    assert outcome.installed is True
    # All required files exist on disk.
    root = get_settings().skills_dir / manifest.skill.name
    for fname in ("SKILL.md", "README.md", "config.yaml"):
        assert (root / fname).is_file(), f"{fname} missing"
    # Registry has the skill.
    skills = SkillRegistry().list_installed()
    assert any(s.name == manifest.skill.name for s in skills)


def test_install_refuses_overwrite_without_flag():
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    second = installer.install(manifest, overwrite=False)
    assert second.installed is False
    assert second.skipped_existing is True


def test_install_overwrites_with_flag():
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    second = installer.install(manifest, overwrite=True)
    assert second.installed is True


def test_install_rejects_invalid_manifest():
    manifest = _plan()
    manifest.skill.name = "backend"  # generic → invalid
    installer = SkillInstaller()
    with pytest.raises(InstallerError):
        installer.install(manifest)


def test_remove_deletes_files_and_registry():
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    assert installer.remove(manifest.skill.name) is True
    root = get_settings().skills_dir / manifest.skill.name
    assert not root.exists()
    assert SkillRegistry().get(manifest.skill.name) is None


def test_remove_nonexistent_returns_false():
    assert SkillInstaller().remove("does-not-exist") is False
