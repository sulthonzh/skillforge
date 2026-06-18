"""Skill packaging — bundle an installed skill into a portable ``.skillpkg``.

A ``.skillpkg`` is a gzipped tarball containing:
  - ``manifest.json``   — the skill's config.yaml as JSON (the SkillManifest)
  - ``SKILL.md``        — the rendered skill doc
  - ``README.md``       — the readme
  - ``config.yaml``     — the original config
  - ``prompts/`` …      — all other generated files
  - ``PACKAGING``       — provenance: name, version, packaged_at, skillforge version

This is the wire format for marketplace publish/download. It round-trips:
pack an installed skill, unpack it back into a SkillManifest + files for install.
"""

from __future__ import annotations

import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ... import __version__
from ...schemas.manifest import (
    Architecture,
    Outputs,
    Safety,
    SkillAI,
    SkillManifest,
    SkillMeta,
    Tool,
)
from ..skill_registry import SkillRegistry


class PackagingError(RuntimeError):
    """Raised when a skill can't be packaged or unpacked."""


class SkillPackager:
    """Pack/unpack ``.skillpkg`` tarballs."""

    def pack(self, skill_name: str) -> bytes:
        """Pack an installed skill into a ``.skillpkg`` tarball. Returns bytes."""
        record = SkillRegistry().get(skill_name)
        if record is None or not Path(record.path).is_dir():
            raise PackagingError(f"No installed skill named {skill_name!r} to package")

        skill_dir = Path(record.path)
        manifest = self._load_manifest(skill_dir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # Provenance file.
            packaging = {
                "name": skill_name,
                "version": manifest.skill.version,
                "packaged_at": datetime.now(timezone.utc).isoformat(),
                "packaged_by": f"skillforge {__version__}",
            }
            self._add_bytes(tar, "PACKAGING", json.dumps(packaging, indent=2).encode())
            # Manifest as JSON (canonical).
            self._add_bytes(
                tar, "manifest.json", manifest.model_dump_json(indent=2).encode()
            )
            # All skill files (SKILL.md, README.md, config.yaml, prompts/, templates/, …).
            for path in sorted(skill_dir.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(skill_dir)
                    tar.add(str(path), arcname=str(rel))
        return buf.getvalue()

    def unpack(self, data: bytes) -> tuple[SkillManifest, dict[str, str]]:
        """Unpack a ``.skillpkg`` into ``(manifest, files)``.

        ``files`` maps relative path → content for every file in the package.
        """
        files: dict[str, str] = {}
        manifest_json: bytes | None = None
        try:
            buf = io.BytesIO(data)
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                # Safe extraction: reject absolute paths / traversal.
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in Path(member.name).parts:
                        raise PackagingError(f"Unsafe path in package: {member.name}")
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    content = f.read()
                    if member.name == "manifest.json":
                        manifest_json = content
                    else:
                        try:
                            files[member.name] = content.decode("utf-8")
                        except UnicodeDecodeError:
                            continue
        except tarfile.TarError as exc:
            raise PackagingError(f"Not a valid .skillpkg: {exc}") from exc

        if manifest_json is None:
            raise PackagingError("Package has no manifest.json")
        manifest = self._parse_manifest(manifest_json)
        return manifest, files

    # ---- helpers ----
    def _load_manifest(self, skill_dir: Path) -> SkillManifest:
        cfg = skill_dir / "config.yaml"
        if not cfg.is_file():
            raise PackagingError(f"No config.yaml in {skill_dir}")
        raw = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise PackagingError(f"{cfg} is not a mapping")
        skill_raw = raw.get("skill") or {}
        arch = raw.get("architecture") or {}
        outputs = raw.get("outputs") or {}
        safety = raw.get("safety") or {}
        ai = raw.get("ai") or {}
        return SkillManifest(
            schema_version=str(raw.get("schema_version", "1.0")),
            skill=SkillMeta(
                name=str(skill_raw.get("name", "")),
                title=str(skill_raw.get("title", "")),
                domain=str(skill_raw.get("domain", "")),
                description=str(skill_raw.get("description", "")),
                version=str(skill_raw.get("version", "0.1.0")),
                status=str(skill_raw.get("status", "installed")),
            ),
            ai=SkillAI(
                generated_by=str(ai.get("generated_by", "skillforge")),
                planner_model=str(ai.get("planner_model", "")),
            ),
            tools=[
                Tool(
                    name=str(t.get("name", "")),
                    category=str(t.get("category", "misc")),
                    enabled=bool(t.get("enabled", True)),
                    reason=str(t.get("reason", "")),
                )
                for t in (raw.get("tools") or [])
            ],
            architecture=Architecture(patterns=list(arch.get("patterns") or [])),
            workflow=list(raw.get("workflow") or []),
            best_practices=list(raw.get("best_practices") or []),
            output_standards=list(raw.get("output_standards") or []),
            outputs=Outputs(
                required_files=list(outputs.get("required_files") or ["SKILL.md", "README.md", "config.yaml"]),
                required_directories=list(outputs.get("required_directories") or ["prompts", "templates", "scripts", "examples"]),
            ),
            safety=Safety(
                auto_execute_scripts=bool(safety.get("auto_execute_scripts", False)),
                require_user_confirmation_before_install=bool(safety.get("require_user_confirmation_before_install", True)),
                allow_network_access=bool(safety.get("allow_network_access", False)),
            ),
            example_prompts=list(raw.get("example_prompts") or []),
            example_outputs=list(raw.get("example_outputs") or []),
        )

    def _parse_manifest(self, data: bytes) -> SkillManifest:
        raw = json.loads(data)
        return SkillManifest.model_validate(raw)

    def _add_bytes(self, tar: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        info.mtime = 0
        tar.addfile(info, io.BytesIO(data))
