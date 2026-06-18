"""Deploy (symlink) installed skills to AI coding tools' skill directories.

Each tool has its own convention for where it looks for skills. This module:

  1. Detects which tools are installed (by checking for their config/skills dirs).
  2. Symlinks a SkillForge skill into each tool's skills dir — one source of
     truth (edit in SkillForge, all tools see it instantly).

Supported tools (auto-detected):
  - Claude Code      ~/.claude/skills/
  - ZCode            ~/.zcode/skills/
  - OpenAI Codex     ~/.codex/skills/
  - OpenCode         ~/.opencode/skills/ or ~/.config/opencode/skills/
  - Aider            ~/.aider/skills/
  - Cursor           ~/.cursor/skills/
  - Continue         ~/.continue/skills/
  - Generic          Any dir matching ~/.*/skills/ that isn't one of the above.

If a tool doesn't follow symlinks, the UI offers a "copy" fallback.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolTarget:
    """An AI coding tool and its skills directory."""

    key: str          # "claude-code", "zcode", etc.
    label: str        # "Claude Code"
    skills_dir: Path  # where this tool looks for skills
    installed: bool   # is the tool itself installed (dir exists)?
    icon: str = ""    # emoji for the UI


# Known tools and their skill dirs (relative to $HOME unless noted).
_KNOWN_TOOLS: list[tuple[str, str, str]] = [
    # (key, label, relative skills path from $HOME)
    ("claude-code", "Claude Code", ".claude/skills"),
    ("zcode", "ZCode", ".zcode/skills"),
    ("codex", "OpenAI Codex", ".codex/skills"),
    ("opencode", "OpenCode", ".opencode/skills"),
    ("aider", "Aider", ".aider/skills"),
    ("cursor", "Cursor", ".cursor/skills"),
    ("continue", "Continue", ".continue/skills"),
    ("cline", "Cline", ".cline/skills"),
    ("windsurf", "Windsurf", ".codeium/windsurf/skills"),
]


def _home() -> Path:
    return Path.home()


class ToolTargetDetector:
    """Detect installed AI coding tools and their skill directories."""

    def detect(self) -> list[ToolTarget]:
        """Return all known tool targets, with ``installed`` flags."""
        home = _home()
        results: list[ToolTarget] = []
        seen_dirs: set[Path] = set()

        for key, label, rel in _KNOWN_TOOLS:
            skills_dir = home / rel
            # A tool is "installed" if its parent config dir exists.
            parent = skills_dir.parent
            installed = parent.is_dir()
            target = ToolTarget(
                key=key,
                label=label,
                skills_dir=skills_dir,
                installed=installed,
            )
            results.append(target)
            seen_dirs.add(skills_dir)

        # Auto-detect generic tools: any ~/.<name>/skills/ that isn't known.
        if home.is_dir():
            for entry in home.iterdir():
                if entry.name.startswith("."):
                        candidate = entry / "skills"
                        if candidate.is_dir() and candidate not in seen_dirs:
                            key = entry.name.lstrip(".")
                            results.append(
                                ToolTarget(
                                    key=f"generic-{key}",
                                    label=f"{key} (auto-detected)",
                                    skills_dir=candidate,
                                    installed=True,
                                )
                            )
                            seen_dirs.add(candidate)

        return results

    def installed_targets(self) -> list[ToolTarget]:
        """Return only tools that are actually installed."""
        return [t for t in self.detect() if t.installed]


class SymlinkDeployer:
    """Symlink (or copy) a skill into a tool's skills directory."""

    def __init__(self, detector: ToolTargetDetector | None = None) -> None:
        self._detector = detector or ToolTargetDetector()

    def deploy(
        self,
        skill_path: str | Path,
        skill_name: str,
        target_key: str | None = None,
        *,
        method: str = "symlink",
    ) -> dict[str, Any]:
        """Deploy a skill to one target (or all installed targets).

        Args:
            skill_path: the source skill directory (in ~/.skillforge/skills/).
            skill_name: the skill name (used as the symlink name).
            target_key: specific tool key, or None for all installed tools.
            method: "symlink" (default) or "copy".
        """
        skill_path = Path(skill_path).resolve()
        if not skill_path.is_dir():
            raise FileNotFoundError(f"Skill not found: {skill_path}")

        targets = self._detector.detect()
        if target_key:
            targets = [t for t in targets if t.key == target_key]
        else:
            targets = [t for t in targets if t.installed]

        results: list[dict[str, Any]] = []
        for target in targets:
            target_dir = target.skills_dir / skill_name
            try:
                self._deploy_one(skill_path, target_dir, method)
                results.append({
                    "target": target.key,
                    "label": target.label,
                    "path": str(target_dir),
                    "method": method,
                    "status": "deployed",
                })
            except Exception as exc:
                results.append({
                    "target": target.key,
                    "label": target.label,
                    "path": str(target_dir),
                    "method": method,
                    "status": "failed",
                    "error": str(exc),
                })
        return {"skill_name": skill_name, "deployments": results}

    def _deploy_one(self, source: Path, target: Path, method: str) -> None:
        """Create or refresh a single symlink/copy."""
        # Remove existing symlink or dir.
        if target.is_symlink() or target.exists():
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)

        target.parent.mkdir(parents=True, exist_ok=True)

        if method == "copy":
            shutil.copytree(source, target)
        else:
            # Symlink (default). On Windows, falls back to copy if symlink fails.
            try:
                target.symlink_to(source, target_is_directory=True)
            except (OSError, NotImplementedError):
                shutil.copytree(source, target)

    def undeploy(self, skill_name: str, target_key: str | None = None) -> dict[str, Any]:
        """Remove a skill symlink from one or all targets."""
        targets = self._detector.detect()
        if target_key:
            targets = [t for t in targets if t.key == target_key]
        else:
            targets = [t for t in targets if t.installed]

        results: list[dict[str, Any]] = []
        for target in targets:
            link = target.skills_dir / skill_name
            removed = False
            if link.is_symlink():
                link.unlink()
                removed = True
            elif link.is_dir():
                # Could be a copy; remove it.
                shutil.rmtree(link, ignore_errors=True)
                removed = True
            elif link.exists():
                link.unlink()
                removed = True
            results.append({
                "target": target.key,
                "label": target.label,
                "path": str(link),
                "status": "removed" if removed else "not_found",
            })
        return {"skill_name": skill_name, "removals": results}

    def status(self, skill_name: str) -> list[dict[str, Any]]:
        """Check deployment status of a skill across all targets."""
        targets = self._detector.detect()
        results: list[dict[str, Any]] = []
        for target in targets:
            link = target.skills_dir / skill_name
            deployed = False
            method = None
            if link.is_symlink():
                deployed = True
                method = "symlink"
            elif link.is_dir():
                deployed = True
                method = "copy"
            results.append({
                "target": target.key,
                "label": target.label,
                "skills_dir": str(target.skills_dir),
                "tool_installed": target.installed,
                "deployed": deployed,
                "method": method,
                "path": str(link) if deployed else None,
            })
        return results


# ---- singletons ----
_detector: ToolTargetDetector | None = None
_deployer: SymlinkDeployer | None = None


def get_detector() -> ToolTargetDetector:
    global _detector
    if _detector is None:
        _detector = ToolTargetDetector()
    return _detector


def get_deployer() -> SymlinkDeployer:
    global _deployer
    if _deployer is None:
        _deployer = SymlinkDeployer()
    return _deployer


def set_deployer(deployer: SymlinkDeployer | None) -> None:
    global _deployer
    _deployer = deployer
