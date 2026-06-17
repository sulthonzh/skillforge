"""Skill installer.

Writes the generated files for a manifest into the configured skills directory
(``~/.skillforge/skills/<name>`` by default) and records the install in the
registry. Safety rules:

- Never overwrite an existing skill unless ``overwrite=True``.
- Never execute generated scripts.
- Validate before writing; refuse to install an invalid skill.

When re-installing (``overwrite=True``) over an existing skill, the version is
auto-bumped based on what changed (see :mod:`versioning`).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..repositories.registry_repository import RegistryRepository
from ..schemas.manifest import SkillManifest
from ..settings import Settings, get_settings
from .skill_generator import GeneratedFile, SkillGenerator
from .skill_validator import SkillValidator, ValidationResult
from .versioning import Bump, classify_change, next_version_for_change


class InstallerError(RuntimeError):
    """Raised when an install cannot proceed safely."""


@dataclass(frozen=True)
class InstallOutcome:
    installed: bool
    path: str
    skipped_existing: bool = False
    previous_version: str | None = None
    new_version: str | None = None
    version_bump: Bump | None = None


class SkillInstaller:
    """Install a manifest's files into the local skills directory."""

    def __init__(
        self,
        generator: SkillGenerator | None = None,
        validator: SkillValidator | None = None,
        repository: RegistryRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._generator = generator or SkillGenerator()
        self._validator = validator or SkillValidator()
        self._repository = repository or RegistryRepository()
        self._settings = settings or get_settings()

    def install(self, manifest: SkillManifest, overwrite: bool = False) -> InstallOutcome:
        # 1) Generate, then validate against the generated files.
        files = self._generator.generate(manifest)
        result = self._validator.validate_manifest(manifest, files)
        if not result.valid:
            raise InstallerError(
                "Manifest failed validation: "
                + "; ".join(i.message for i in result.errors)
            )

        # 2) Resolve the target directory.
        target = self._settings.skills_dir / manifest.skill.name
        existed = target.exists()
        if existed and not overwrite:
            return InstallOutcome(installed=False, path=str(target), skipped_existing=True)

        # 2b) Auto-bump the version when overwriting an existing skill. We classify
        # the change against the previously-installed manifest and bump accordingly.
        previous_version: str | None = None
        bump: Bump | None = None
        if existed and overwrite:
            previous_version, bump = self._compute_bump(manifest, target)
            if bump is not None:
                new_version = next_version_for_change(previous_version, bump)
                bumped_skill = manifest.skill.model_copy(update={"version": new_version})
                manifest = manifest.model_copy(update={"skill": bumped_skill})
                # Re-generate files so config.yaml carries the bumped version.
                files = self._generator.generate(manifest)

            # Defense in depth: a stale dir at the path is replaced only when overwrite=True.
            shutil.rmtree(target)

        # 3) Write the files.
        _write_files(target, files)

        # 4) Record in the registry.
        self._repository.upsert(
            name=manifest.skill.name,
            title=manifest.skill.title,
            domain=manifest.skill.domain,
            version=manifest.skill.version,
            path=str(target),
        )

        return InstallOutcome(
            installed=True,
            path=str(target),
            previous_version=previous_version,
            new_version=manifest.skill.version if bump else None,
            version_bump=bump,
        )

    def _compute_bump(self, manifest: SkillManifest, target: Path) -> tuple[str | None, Bump | None]:
        """Classify the change vs. the installed config.yaml and return (prev_version, bump)."""
        prev_config = target / "config.yaml"
        if not prev_config.is_file():
            return None, None
        try:
            prev_raw = yaml.safe_load(prev_config.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return None, None
        prev_skill = prev_raw.get("skill") or {}
        prev_version = str(prev_skill.get("version", "0.1.0"))
        prev_tools = [str(t.get("name", "")) for t in (prev_raw.get("tools") or [])]
        prev_text = _textual_fingerprint(prev_raw)
        new_text = _textual_fingerprint(
            {
                "workflow": manifest.workflow,
                "best_practices": manifest.best_practices,
                "output_standards": manifest.output_standards,
                "architecture": {"patterns": manifest.architecture.patterns},
                "description": manifest.skill.description,
            }
        )
        bump = classify_change(
            old_name=str(prev_skill.get("name", "")),
            new_name=manifest.skill.name,
            old_domain=str(prev_skill.get("domain", "")),
            new_domain=manifest.skill.domain,
            old_tool_names=prev_tools,
            new_tool_names=[t.name for t in manifest.tools],
            text_changed=prev_text != new_text,
        )
        return prev_version, bump

    def validate_only(self, manifest: SkillManifest) -> ValidationResult:
        files = self._generator.generate(manifest)
        return self._validator.validate_manifest(manifest, files)

    def remove(self, name: str) -> bool:
        record = self._repository.get(name)
        target = Path(record.path) if record else (self._settings.skills_dir / name)
        removed_fs = False
        if target.exists():
            shutil.rmtree(target)
            removed_fs = True
        removed_db = self._repository.delete(name)
        return removed_fs or removed_db


def _write_files(target_root, files: list[GeneratedFile]) -> None:
    root = Path(target_root)
    root.mkdir(parents=True, exist_ok=True)
    for file in files:
        path = root / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content, encoding="utf-8")


def _textual_fingerprint(raw: dict) -> str:
    """A stable string capturing the non-tool fields used to detect text edits."""
    import json

    return json.dumps(
        {
            "description": str(raw.get("description", "")),
            "workflow": list(raw.get("workflow") or []),
            "best_practices": list(raw.get("best_practices") or []),
            "output_standards": list(raw.get("output_standards") or []),
            "patterns": list((raw.get("architecture") or {}).get("patterns") or []),
        },
        sort_keys=True,
    )
