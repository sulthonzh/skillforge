"""Skill validator.

A skill is valid when it has the required files, a kebab-case non-generic name,
at least one domain, at least two tools, and the required ``SKILL.md`` sections.
The validator works on either a manifest (in-memory) or an installed skill
directory (filesystem).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..schemas.manifest import GENERIC_NAMES, SkillManifest
from .skill_generator import GeneratedFile

# Required top-level sections in SKILL.md (case-insensitive markdown headers).
REQUIRED_SECTIONS = (
    "Purpose",
    "When to Use",
    "Tools and Stack",
    "Workflow",
    "Best Practices",
    "Output Standards",
)

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]+(?:-[a-z0-9]+)+$")

REQUIRED_FILES = ("SKILL.md", "README.md", "config.yaml")


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"  # error | warning

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "message": self.message}


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def add(self, code: str, message: str, severity: str = "error") -> None:
        self.issues.append(ValidationIssue(severity=severity, code=code, message=message))


class SkillValidator:
    """Validate manifests and installed skill folders."""

    # ------------------------------------------------------------------ manifest
    def validate_manifest(
        self,
        manifest: SkillManifest,
        files: list[GeneratedFile] | None = None,
    ) -> ValidationResult:
        result = ValidationResult()

        # Name format.
        name = manifest.skill.name
        if not KEBAB_RE.match(name):
            result.add(
                "name_format",
                f"Skill name {name!r} must be kebab-case with at least two segments "
                "(e.g. 'backend-fastapi-postgres').",
            )
        # Generic name.
        if name in GENERIC_NAMES:
            result.add("name_generic", f"Skill name {name!r} is too generic. Be specific.")
        # Domain.
        if not manifest.skill.domain.strip():
            result.add("domain_missing", "Skill must declare at least one domain.")
        # Tools (>=2).
        enabled = [t for t in manifest.tools if t.enabled]
        if len(enabled) < 2:
            result.add(
                "tools_too_few",
                "Skill must recommend at least two enabled tools "
                f"(found {len(enabled)}).",
            )
        # Workflow non-empty.
        if not manifest.workflow:
            result.add("workflow_missing", "Skill must include a workflow.")
        # Files map.
        file_map: dict[str, str] = {}
        if files:
            file_map = {f.path: f.content for f in files}

        # config.yaml present (either as a generated file or implicit).
        config_text = file_map.get("config.yaml")
        if config_text is not None:
            try:
                parsed = yaml.safe_load(config_text)
            except yaml.YAMLError as exc:
                result.add("config_invalid_yaml", f"config.yaml is not valid YAML: {exc}")
            else:
                if not isinstance(parsed, dict):
                    result.add("config_shape", "config.yaml must be a mapping.")
        else:
            # No preview files supplied; we cannot fully check the config.
            result.add("config_missing_preview", "config.yaml was not included for validation.", severity="warning")

        # SKILL.md sections.
        skill_md = file_map.get("SKILL.md", "")
        if skill_md:
            missing = [s for s in REQUIRED_SECTIONS if not _has_section(skill_md, s)]
            if missing:
                result.add(
                    "skill_md_sections",
                    f"SKILL.md is missing required sections: {', '.join(missing)}.",
                )
        else:
            result.add("skill_md_missing_preview", "SKILL.md was not included for validation.", severity="warning")

        return result

    # ------------------------------------------------------------------ filesystem
    def validate_directory(self, skill_dir: str | Path) -> ValidationResult:
        result = ValidationResult()
        path = Path(skill_dir)
        if not path.is_dir():
            result.add("not_a_directory", f"{path} is not a directory.")
            return result

        # Required files exist.
        for fname in REQUIRED_FILES:
            if not (path / fname).is_file():
                result.add("file_missing", f"Required file {fname!r} is missing in {path}.")

        # config.yaml parses and has a kebab-case name.
        config_path = path / "config.yaml"
        if config_path.is_file():
            try:
                text = config_path.read_text(encoding="utf-8")
                parsed = yaml.safe_load(text) or {}
            except yaml.YAMLError as exc:
                result.add("config_invalid_yaml", f"config.yaml is not valid YAML: {exc}")
            else:
                if not isinstance(parsed, dict):
                    result.add("config_shape", "config.yaml must be a mapping.")
                else:
                    skill = parsed.get("skill") or {}
                    name = str(skill.get("name", "")).strip()
                    if not name:
                        result.add("name_missing", "config.yaml has no skill.name.")
                    else:
                        if not KEBAB_RE.match(name):
                            result.add("name_format", f"Skill name {name!r} is not kebab-case.")
                        if name in GENERIC_NAMES:
                            result.add("name_generic", f"Skill name {name!r} is too generic.")

        # SKILL.md sections.
        skill_md_path = path / "SKILL.md"
        if skill_md_path.is_file():
            text = skill_md_path.read_text(encoding="utf-8")
            missing = [s for s in REQUIRED_SECTIONS if not _has_section(text, s)]
            if missing:
                result.add(
                    "skill_md_sections",
                    f"SKILL.md is missing required sections: {', '.join(missing)}.",
                )

        return result


def _has_section(markdown: str, section: str) -> bool:
    """Return True if *markdown* has a header whose text matches *section*."""
    pattern = re.compile(rf"^#+\s*{re.escape(section)}\s*$", re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(markdown))
