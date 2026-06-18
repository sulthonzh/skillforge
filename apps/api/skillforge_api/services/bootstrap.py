"""First-run bootstrap.

On startup, if no `skill-creator` skill is installed, generate one with the
planner and install it. This makes SkillForge self-bootstrapping: the product's
own example skill is produced by the product itself, and the user immediately
sees a concrete installed skill in the registry.

The bootstrap is idempotent — it never overwrites an existing skill-creator.
"""

from __future__ import annotations

import logging

from .ai_skill_planner import AISkillPlanner
from .skill_installer import SkillInstaller

log = logging.getLogger(__name__)

SKILL_CREATOR_MESSAGE = (
    "I need a meta-skill called skill-creator that helps engineers author, "
    "structure, and validate new SkillForge skills. It should cover skill "
    "manifest design, the SKILL.md section contract, tool selection, "
    "kebab-case naming, and a validation checklist. Tools: Python, PyYAML, "
    "Jinja2, Pydantic, FastAPI."
)

EXPECTED_NAME = "skill-creator"


def bootstrap_skill_creator(force: bool = False) -> bool:
    """Install the generated skill-creator skill if absent.

    Returns True if it was (re)installed this call. Safe to call on every
    startup — it short-circuits when the skill already exists.
    """
    try:
        installer = SkillInstaller()
        # Already installed? Short-circuit (idempotent).
        from .skill_registry import SkillRegistry

        registry = SkillRegistry(installer=installer)
        if not force and registry.get(EXPECTED_NAME) is not None:
            return False

        # Use the *active* provider (mock by default → works offline).
        planner = AISkillPlanner()
        manifest, _ = planner.plan(SKILL_CREATOR_MESSAGE)
        # Pin the canonical name regardless of what the planner derived.
        manifest.skill.name = EXPECTED_NAME
        manifest.skill.title = "Skill Creator"
        manifest.skill.description = (
            "Helps engineers author, structure, and validate new SkillForge skills: "
            "manifest design, the SKILL.md contract, tool selection, naming, and validation."
        )
        # This is a meta-skill; mark it as ready.
        manifest.skill.status = "ready"

        outcome = installer.install(manifest, overwrite=force)
        if outcome.installed:
            log.info("Bootstrapped skill-creator at %s", outcome.path)
            return True
        if outcome.skipped_existing:
            return False
        return False
    except Exception as exc:  # pragma: no cover - bootstrap must never break startup
        log.warning("Could not bootstrap skill-creator: %s", exc)
        return False
