"""Skill installer.

Writes the generated files for a manifest into the configured skills directory
(``~/.skillforge/skills/<name>`` by default) and records the install in the
registry. Safety rules:

- Never overwrite an existing skill unless ``overwrite=True``.
- Never execute generated scripts.
- Validate before writing; refuse to install an invalid skill.
- **Atomic install**: files are written to a sibling staging dir and swapped
  into place with ``os.replace`` (atomic rename). A failure mid-write leaves
  the previously-installed skill untouched — no half-installed skills, no
  deleted-then-failed gaps. (Tier 0.3.)

When re-installing (``overwrite=True``) over an existing skill, the version is
auto-bumped based on what changed (see :mod:`versioning`).
"""

from __future__ import annotations

import os
import secrets
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

        # 3) Write files atomically: stage → rename. A failure during _write_files
        # leaves the previously-installed skill (if any) untouched on disk.
        # os.replace is an atomic rename on POSIX (and on Windows for same-FS
        # dirs), so there's no window where the target doesn't exist.
        staging = target.parent / f".{target.name}.staging-{os.getpid()}-{secrets.token_hex(4)}"
        backup: Path | None = None
        try:
            _write_files(staging, files)
            if existed:
                # Move the old skill aside (also atomic). If anything below fails,
                # we restore it so the user's previous skill survives.
                backup = target.parent / f".{target.name}.backup-{os.getpid()}-{secrets.token_hex(4)}"
                os.replace(target, backup)
            os.replace(staging, target)
            staging = None  # consumed by the rename
        finally:
            # Clean up: staging dir if the rename didn't happen, and the backup
            # only AFTER the new target is in place + registry updated (below).
            if staging is not None and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            if backup is not None and backup.exists():
                shutil.rmtree(backup, ignore_errors=True)

        # 4) Record in the registry — only AFTER the filesystem is consistent.
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
        """Classify the change vs. the installed config.yaml and return (prev_version, bump).

        Raises ``InstallerError`` if the existing config.yaml is malformed — we
        used to silently return ``(None, None)`` and skip the bump, which hid a
        real problem (corrupt install) from the user. Missing config.yaml still
        returns ``(None, None)`` since that's a legitimate "no prior version"
        state (e.g. a hand-created dir).
        """
        prev_config = target / "config.yaml"
        if not prev_config.is_file():
            return None, None
        try:
            prev_raw = yaml.safe_load(prev_config.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise InstallerError(
                f"Cannot read existing {prev_config.name} to compute version bump "
                f"(it is malformed YAML): {exc}. Remove the skill and reinstall."
            ) from exc
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
        """Remove a skill. The registry row is deleted BEFORE the filesystem.

        Ordering rationale: if the DB delete fails, the skill files stay on
        disk (recoverable, and the registry no longer points at them either
        since delete is idempotent). If we removed files first and the DB
        delete then failed, we'd leave a dangling registry row pointing at a
        missing path — worse failure mode.
        """
        record = self._repository.get(name)
        target = Path(record.path) if record else (self._settings.skills_dir / name)
        # Delete the registry row first.
        removed_db = self._repository.delete(name)
        # Then remove the files.
        removed_fs = False
        if target.exists():
            shutil.rmtree(target)
            removed_fs = True
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
