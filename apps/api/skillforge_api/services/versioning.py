"""Semantic version bumping for skill edits.

Given the previous version and a measure of how much changed, produce the next
version. The bump level adapts to the diff:

  patch  — description / reasons / workflow / best-practice text changed
           (same identity, same tool set)
  minor  — tools added or removed (the stack changed)
  major  — the skill's identity changed (name or domain)

Versions are ``MAJOR.MINOR.PATCH``. A non-conforming previous version falls back
to a patch bump so we never produce something invalid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Bump:
    level: str  # "patch" | "minor" | "major"
    reason: str


def parse_version(v: str) -> tuple[int, int, int] | None:
    m = _VERSION_RE.match((v or "").strip().lstrip("v"))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_version(previous: str, level: str = "patch") -> str:
    """Return the next version string for *previous* at *level*."""
    parsed = parse_version(previous)
    if parsed is None:
        # Unknown shape — start from 0.1.0 and apply one bump.
        parsed = (0, 1, 0)
        level = "patch"
    major, minor, patch = parsed
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def classify_change(
    *,
    old_name: str,
    new_name: str,
    old_domain: str,
    new_domain: str,
    old_tool_names: list[str],
    new_tool_names: list[str],
    text_changed: bool,
) -> Bump:
    """Decide the bump level from what changed between two manifests.

    Identity change → major; tool set change → minor; else text → patch.
    """
    if (old_name or "").strip() != (new_name or "").strip():
        return Bump("major", f"skill renamed ({old_name} → {new_name})")
    if (old_domain or "").strip() != (new_domain or "").strip():
        return Bump("major", f"domain changed ({old_domain} → {new_domain})")
    old_set = {t.lower() for t in old_tool_names}
    new_set = {t.lower() for t in new_tool_names}
    if old_set != new_set:
        added = new_set - old_set
        removed = old_set - new_set
        parts = []
        if added:
            parts.append(f"+{len(added)} tool(s)")
        if removed:
            parts.append(f"-{len(removed)} tool(s)")
        return Bump("minor", "tool set changed (" + ", ".join(parts) + ")")
    if text_changed:
        return Bump("patch", "details updated (workflow / practices / reasons)")
    return Bump("patch", "no material change detected")


def next_version_for_change(previous: str, bump: Bump) -> str:
    return bump_version(previous, bump.level)
