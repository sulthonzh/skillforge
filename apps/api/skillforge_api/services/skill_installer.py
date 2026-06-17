"""Skill installer.

Writes the generated files for a manifest into the configured skills directory
(``~/.skillforge/skills/<name>`` by default) and records the install in the
registry. Safety rules:

- Never overwrite an existing skill unless ``overwrite=True``.
- Never execute generated scripts.
- Validate before writing; refuse to install an invalid skill.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..repositories.registry_repository import RegistryRepository
from ..schemas.manifest import SkillManifest
from ..settings import Settings, get_settings
from .skill_generator import GeneratedFile, SkillGenerator
from .skill_validator import SkillValidator, ValidationResult


class InstallerError(RuntimeError):
    """Raised when an install cannot proceed safely."""


@dataclass(frozen=True)
class InstallOutcome:
    installed: bool
    path: str
    skipped_existing: bool = False


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
        if target.exists() and not overwrite:
            return InstallOutcome(installed=False, path=str(target), skipped_existing=True)
        # Defense in depth: a stale dir at the path is replaced only when overwrite=True.
        if target.exists() and overwrite:
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

        return InstallOutcome(installed=True, path=str(target))

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
