"""Tests for the skill validator."""

from __future__ import annotations

from skillforge_api.schemas.manifest import (
    SkillManifest,
    Tool,
)
from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_generator import SkillGenerator
from skillforge_api.services.skill_validator import SkillValidator


def _valid_manifest() -> SkillManifest:
    manifest, _ = AISkillPlanner().plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )
    return manifest


def test_valid_manifest_passes():
    manifest = _valid_manifest()
    files = SkillGenerator().generate(manifest)
    result = SkillValidator().validate_manifest(manifest, files)
    assert result.valid, [i.message for i in result.errors]


def test_rejects_generic_name():
    manifest = _valid_manifest()
    manifest.skill.name = "backend"
    result = SkillValidator().validate_manifest(manifest)
    codes = [i.code for i in result.errors]
    assert "name_generic" in codes


def test_rejects_bad_name_format():
    manifest = _valid_manifest()
    manifest.skill.name = "BackendSkill"  # camelCase, not kebab
    result = SkillValidator().validate_manifest(manifest)
    codes = [i.code for i in result.errors]
    assert "name_format" in codes


def test_rejects_single_segment_name():
    manifest = _valid_manifest()
    manifest.skill.name = "backend"  # only one segment
    result = SkillValidator().validate_manifest(manifest)
    codes = [i.code for i in result.errors]
    assert "name_format" in codes or "name_generic" in codes


def test_rejects_too_few_tools():
    manifest = _valid_manifest()
    manifest.tools = [Tool(name="Python", category="languages")]
    result = SkillValidator().validate_manifest(manifest)
    codes = [i.code for i in result.errors]
    assert "tools_too_few" in codes


def test_rejects_missing_domain():
    manifest = _valid_manifest()
    manifest.skill.domain = ""
    result = SkillValidator().validate_manifest(manifest)
    codes = [i.code for i in result.errors]
    assert "domain_missing" in codes


def test_rejects_missing_workflow():
    manifest = _valid_manifest()
    manifest.workflow = []
    result = SkillValidator().validate_manifest(manifest)
    codes = [i.code for i in result.errors]
    assert "workflow_missing" in codes


def test_detects_missing_skill_md_sections():
    manifest = _valid_manifest()
    from skillforge_api.services.skill_generator import GeneratedFile

    bad_skill_md = GeneratedFile(path="SKILL.md", content="# Title\n\nNo sections here.")
    config = GeneratedFile(
        path="config.yaml",
        content="skill: {name: backend-fastapi-postgresql}\n",
    )
    result = SkillValidator().validate_manifest(manifest, [bad_skill_md, config])
    codes = [i.code for i in result.errors]
    assert "skill_md_sections" in codes


def test_validate_directory_on_nonexistent_path(tmp_path):
    result = SkillValidator().validate_directory(tmp_path / "nope")
    assert not result.valid
