"""Tool catalog loader.

Loads ``data/tool_catalog.yaml`` once and exposes convenient accessors used by
the AI planner. The catalog is intentionally a plain editable YAML file so OSS
contributors can extend SkillForge without touching code.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml


class CatalogError(RuntimeError):
    """Raised when the tool catalog cannot be loaded or is malformed."""


class ToolCatalog:
    """In-memory view of the tool catalog."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        domains = raw.get("domains") or {}
        if not isinstance(domains, dict):
            raise CatalogError("`domains` must be a mapping in tool_catalog.yaml")
        self._domains: dict[str, dict[str, Any]] = domains

    # ---- introspection ----
    @property
    def domains(self) -> dict[str, dict[str, Any]]:
        return self._domains

    def domain_keys(self) -> list[str]:
        return list(self._domains.keys())

    def domain_label(self, key: str) -> str:
        entry = self._domains.get(key, {})
        return entry.get("label", key)

    def categories(self, domain_key: str) -> list[str]:
        entry = self._domains.get(domain_key, {})
        return list((entry.get("recommended_tools") or {}).keys())

    def tools_for(self, domain_key: str, category: str) -> list[str]:
        entry = self._domains.get(domain_key, {})
        tools = (entry.get("recommended_tools") or {}).get(category) or []
        return list(tools)

    def all_tools(self) -> list[str]:
        seen: list[str] = []
        for entry in self._domains.values():
            for tools in (entry.get("recommended_tools") or {}).values():
                for t in tools:
                    if t not in seen:
                        seen.append(t)
        return seen

    # ---- matching helpers ----
    def find_domain(self, text: str) -> str | None:
        """Return the best-matching domain key for free text, or ``None``."""
        lowered = (text or "").lower()
        if not lowered:
            return None
        best_key: str | None = None
        best_score = 0
        for key, entry in self._domains.items():
            haystacks = [key.lower(), str(entry.get("label", "")).lower()]
            haystacks += [str(k).lower() for k in entry.get("keywords") or []]
            score = sum(lowered.count(h) for h in haystacks if h)
            # Strong direct match on the domain key/label.
            if key.lower() in lowered or str(entry.get("label", "")).lower() in lowered:
                score += 10
            if score > best_score:
                best_score = score
                best_key = key
        return best_key if best_score > 0 else None

    def find_tools_in_text(self, text: str) -> list[tuple[str, str]]:
        """Return ``(tool_name, category)`` pairs whose name appears in *text*."""
        lowered = (text or "").lower()
        found: list[tuple[str, str]] = []
        for entry in self._domains.values():
            for category, tools in (entry.get("recommended_tools") or {}).items():
                for tool in tools:
                    token = tool.lower()
                    # Word-ish boundary match so "Go" doesn't match every "going".
                    if _contains_word(lowered, token):
                        pair = (tool, category)
                        if pair not in found:
                            found.append(pair)
        return found


# Match runs of word characters plus the chars that legitimately appear in tool
# names (".", "+", "-") but NOT spaces, so each match is a single token.
_WORD_TOKEN_RE = re.compile(r"[a-z0-9.+-]+", re.IGNORECASE)


def _contains_word(haystack: str, token: str) -> bool:
    """Return True if *token* appears as a word/phrase in *haystack*.

    Matches on whole-word boundaries so "Go" doesn't match "going". Compares
    case-insensitively. Multi-word tokens (e.g. "GitHub Actions") match via a
    normalized substring check that treats any non-alphanumeric run as a space.
    """
    if not token:
        return False
    token_l = token.lower()
    hay_l = haystack.lower()

    # Single-word token: compare against every word token in the haystack.
    if " " not in token_l:
        return any(match == token_l for match in _WORD_TOKEN_RE.findall(hay_l))

    # Multi-word token: normalize whitespace runs in the haystack and substring-match.
    normalized = re.sub(r"[^a-z0-9.+ -]+", " ", hay_l)
    normalized = re.sub(r"\s+", " ", normalized)
    return token_l in normalized


def load_catalog(path: str | Path | None = None) -> ToolCatalog:
    """Load the tool catalog from *path* or the packaged ``data`` file."""
    if path is not None:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
    else:
        # Prefer importlib.resources for packaged data.
        try:
            text = (
                resources.files("skillforge_api")
                .joinpath("data/tool_catalog.yaml")
                .read_text(encoding="utf-8")
            )
        except (FileNotFoundError, ModuleNotFoundError):
            # Fallback: path relative to this file.
            fallback = Path(__file__).resolve().parent.parent / "data" / "tool_catalog.yaml"
            text = fallback.read_text(encoding="utf-8")

    raw = yaml.safe_load(text) or {}
    if not isinstance(raw, dict):
        raise CatalogError("tool_catalog.yaml must contain a mapping at the top level")
    return ToolCatalog(raw)


@lru_cache(maxsize=4)
def get_catalog() -> ToolCatalog:
    """Return a process-wide cached catalog (loaded from the packaged file)."""
    return load_catalog()
