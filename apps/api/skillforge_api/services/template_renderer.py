"""Jinja2 template renderer.

Loads the bundled ``templates/*.j2`` files and renders them against a
:class:`SkillManifest`. The renderer is intentionally tiny — all heavy lifting
lives in the templates themselves so they stay editable by contributors.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib import resources
from pathlib import Path

from jinja2 import Environment, StrictUndefined, Template

from ..schemas.manifest import SkillManifest


class TemplateError(RuntimeError):
    """Raised when a template cannot be loaded or rendered."""


class TemplateRenderer:
    """Render Jinja2 templates against a manifest.

    Autoescaping is disabled because every rendered file is markdown or YAML
    (never HTML), and enabling it would corrupt quotes into HTML entities.
    """

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        self._templates_dir = Path(templates_dir) if templates_dir else None
        self._env = Environment(
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    # ---- public API ----
    def render(self, template_name: str, manifest: SkillManifest) -> str:
        template = self._load(template_name)
        try:
            return template.render(**self._context(manifest))
        except Exception as exc:  # pragma: no cover - re-raised as TemplateError
            raise TemplateError(f"Failed to render {template_name!r}: {exc}") from exc

    def render_many(self, items: Iterable[tuple[str, str]], manifest: SkillManifest) -> dict[str, str]:
        out: dict[str, str] = {}
        for template_name, target_path in items:
            out[target_path] = self.render(template_name, manifest)
        return out

    # ---- internals ----
    def _load(self, name: str) -> Template:
        if self._templates_dir is not None:
            path = self._templates_dir / name
            if not path.exists():
                raise TemplateError(f"Template not found: {path}")
            return self._env.from_string(path.read_text(encoding="utf-8"))
        # Packaged templates via importlib.resources.
        try:
            text = (
                resources.files("skillforge_api")
                .joinpath(f"templates/{name}")
                .read_text(encoding="utf-8")
            )
        except (FileNotFoundError, ModuleNotFoundError) as exc:
            raise TemplateError(f"Template not found: {name}") from exc
        return self._env.from_string(text)

    @staticmethod
    def _context(manifest: SkillManifest) -> dict:
        tools = [t for t in manifest.tools if t.enabled]
        return {
            "manifest": manifest,
            "skill": manifest.skill,
            "tools": tools,
            "enabled_tools": tools,
            "architecture": manifest.architecture,
            "workflow": manifest.workflow,
            "best_practices": manifest.best_practices,
            "output_standards": manifest.output_standards,
            "outputs": manifest.outputs,
            "safety": manifest.safety,
            "example_prompts": manifest.example_prompts,
            "example_outputs": manifest.example_outputs,
            "ai": manifest.ai,
        }
