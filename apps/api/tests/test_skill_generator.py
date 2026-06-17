"""Tests for the skill generator."""

from __future__ import annotations

import yaml

from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_generator import SkillGenerator


def _plan():
    manifest, _ = AISkillPlanner().plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )
    return manifest


def test_generator_produces_required_files():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    paths = {f.path for f in files}
    assert {"SKILL.md", "README.md", "config.yaml"} <= paths


def test_generator_creates_required_directories():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    dirs = {f.path.split("/")[0] for f in files if "/" in f.path}
    assert {"prompts", "templates", "scripts", "examples"} <= dirs


def test_generated_config_is_valid_yaml():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    config = next(f for f in files if f.path == "config.yaml")
    parsed = yaml.safe_load(config.content)
    assert isinstance(parsed, dict)
    assert parsed["skill"]["name"] == manifest.skill.name
    assert parsed["schema_version"] == "1.0"
    # Safety defaults preserved.
    assert parsed["safety"]["auto_execute_scripts"] is False


def test_generated_skill_md_has_required_sections():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    skill_md = next(f for f in files if f.path == "SKILL.md").content
    for section in ("Purpose", "When to Use", "Tools and Stack", "Workflow", "Best Practices", "Output Standards"):
        assert section.lower() in skill_md.lower(), f"missing section: {section}"


def test_generator_emits_stack_specific_templates():
    manifest = _plan()
    files = SkillGenerator().generate(manifest)
    template_names = {f.path for f in files if f.path.startswith("templates/")}
    # FastAPI stack → router scaffold present.
    assert "templates/router.py.j2" in template_names
    assert "templates/service.py.j2" in template_names


def test_generator_handles_manifest_with_special_chars():
    """Description with quotes/colons must not corrupt config.yaml."""
    manifest = _plan()
    manifest.skill.description = 'Tricky: a "quoted" description with: colons'
    files = SkillGenerator().generate(manifest)
    config = next(f for f in files if f.path == "config.yaml")
    # Must round-trip through YAML cleanly.
    parsed = yaml.safe_load(config.content)
    assert parsed["skill"]["description"] == 'Tricky: a "quoted" description with: colons'
