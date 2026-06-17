"""Skill generator.

Given a :class:`SkillManifest`, produce the full set of files that make up an
installed skill:

    SKILL.md
    README.md
    config.yaml
    prompts/<domain>.md            (a few starter prompts)
    templates/<name>.j2            (scaffold templates tied to the tools)
    scripts/README.md              (reference-only scripts; never auto-executed)
    examples/example-user-prompts.md

The generator is pure: it returns a list of (path, content) pairs and touches
nothing on disk. The installer writes them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from ..schemas.manifest import SkillManifest, Tool
from .template_renderer import TemplateRenderer


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: str


class SkillGenerator:
    """Render the full file tree for a skill manifest."""

    # Markdown templates that map to a fixed output path. ``config.yaml`` is
    # generated via PyYAML (see :meth:`_config_yaml`) so it is always valid.
    TEMPLATE_MAP: list[tuple[str, str]] = [
        ("skill.md.j2", "SKILL.md"),
        ("readme.md.j2", "README.md"),
    ]

    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self._renderer = renderer or TemplateRenderer()

    def generate(self, manifest: SkillManifest) -> list[GeneratedFile]:
        files: list[GeneratedFile] = []

        # 1) Markdown files from Jinja2 templates.
        for template_name, target in self.TEMPLATE_MAP:
            files.append(GeneratedFile(target, self._renderer.render(template_name, manifest)))

        # 2) config.yaml via PyYAML — guaranteed valid for any manifest content.
        files.append(GeneratedFile("config.yaml", self._config_yaml(manifest)))

        # 3) prompts/ — a small set of starter prompts keyed by domain + tools.
        for name, body in self._prompt_files(manifest):
            files.append(GeneratedFile(f"prompts/{name}", body))

        # 4) templates/ — code scaffolds that reflect the chosen stack.
        for name, body in self._template_files(manifest):
            files.append(GeneratedFile(f"templates/{name}", body))

        # 5) scripts/README.md — reference-only scripts (never auto-executed).
        files.append(GeneratedFile("scripts/README.md", self._scripts_readme(manifest)))

        # 6) examples/example-user-prompts.md — generated from the examples template.
        files.append(
            GeneratedFile(
                "examples/example-user-prompts.md",
                self._renderer.render("examples.md.j2", manifest),
            )
        )

        return files

    # ------------------------------------------------------------------ config
    def _config_yaml(self, manifest: SkillManifest) -> str:
        """Render ``config.yaml`` from the manifest using PyYAML.

        Using PyYAML (rather than a Jinja template) guarantees the output is
        always valid YAML regardless of quotes, colons, or unicode in tool
        names, reasons, or the description.
        """
        tools = manifest.enabled_tools or manifest.tools
        data = {
            "schema_version": manifest.schema_version,
            "skill": {
                "name": manifest.skill.name,
                "title": manifest.skill.title,
                "domain": manifest.skill.domain,
                "description": manifest.skill.description,
                "version": manifest.skill.version,
                "status": manifest.skill.status,
            },
            "ai": {
                "generated_by": manifest.ai.generated_by,
                "planner_model": manifest.ai.planner_model,
                "created_at": manifest.ai.created_at.isoformat() if manifest.ai.created_at else None,
            },
            "tools": [
                {
                    "name": t.name,
                    "category": t.category,
                    "enabled": t.enabled,
                    "reason": t.reason,
                }
                for t in tools
            ],
            "architecture": {"patterns": list(manifest.architecture.patterns)},
            "workflow": list(manifest.workflow),
            "best_practices": list(manifest.best_practices),
            "output_standards": list(manifest.output_standards),
            "outputs": {
                "required_files": list(manifest.outputs.required_files),
                "required_directories": list(manifest.outputs.required_directories),
            },
            "safety": {
                "auto_execute_scripts": manifest.safety.auto_execute_scripts,
                "require_user_confirmation_before_install": manifest.safety.require_user_confirmation_before_install,
                "allow_network_access": manifest.safety.allow_network_access,
            },
            "example_prompts": list(manifest.example_prompts),
            "example_outputs": list(manifest.example_outputs),
        }
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)

    # ------------------------------------------------------------------ prompts
    def _prompt_files(self, manifest: SkillManifest) -> list[tuple[str, str]]:
        domain = _slug(manifest.skill.domain)
        tools = manifest.enabled_tools or manifest.tools
        primary = tools[0].name if tools else "the recommended stack"
        secondary = tools[1].name if len(tools) > 1 else "supporting tools"

        starters: list[tuple[str, str]] = []
        starters.append(
            (
                f"{domain}-design.md",
                _DESIGN_PROMPT.format(skill=manifest.skill.title, primary=primary),
            )
        )
        starters.append(
            (
                f"{domain}-implement.md",
                _IMPLEMENT_PROMPT.format(skill=manifest.skill.title, primary=primary, secondary=secondary),
            )
        )
        starters.append(
            (
                f"{domain}-test.md",
                _TEST_PROMPT.format(skill=manifest.skill.title, primary=primary),
            )
        )
        return starters

    # ------------------------------------------------------------------ templates
    def _template_files(self, manifest: SkillManifest) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        tool_names = {t.name.lower() for t in (manifest.enabled_tools or manifest.tools)}

        # Code templates depend on the chosen language/framework. Emit only
        # scaffolds that match the chosen stack so files stay relevant.
        if "python" in tool_names or "fastapi" in tool_names or "django" in tool_names:
            out.append(("service.py.j2", _PY_SERVICE))
            out.append(("repository.py.j2", _PY_REPOSITORY))
            if "fastapi" in tool_names:
                out.append(("router.py.j2", _FASTAPI_ROUTER))
        if "go" in tool_names or "gin" in tool_names or "fiber" in tool_names:
            out.append(("handler.go.j2", _GO_HANDLER))
        if "typescript" in tool_names or "next.js" in tool_names or "react" in tool_names:
            out.append(("component.tsx.j2", _TS_COMPONENT))
        if "airflow" in tool_names or "dagster" in tool_names:
            out.append(("pipeline.py.j2", _PIPELINE))
        if "dbt" in tool_names:
            out.append(("model.sql.j2", _DBT_MODEL))
        if "terraform" in tool_names or "opentofu" in tool_names:
            out.append(("main.tf.j2", _TERRAFORM))
        if "docker" in tool_names:
            out.append(("Dockerfile.j2", _DOCKERFILE))
        if "langchain" in tool_names or "llamaindex" in tool_names:
            out.append(("rag_chain.py.j2", _RAG_CHAIN))

        # Always include a config snippet template so users have a starting point.
        out.append(("config.example.yaml.j2", _CONFIG_EXAMPLE))
        return out

    # ------------------------------------------------------------------ scripts
    def _scripts_readme(self, manifest: SkillManifest) -> str:
        tools = ", ".join(t.name for t in (manifest.enabled_tools or manifest.tools)[:6]) or "the recommended tools"
        return _SCRIPTS_README.format(skill=manifest.skill.title, tools=tools)


# ----------------------------------------------------------------------------
# Embedded reference scaffolds
#
# These are intentionally minimal. They exist so a freshly generated skill has
# concrete, editable starting points that match its stack. SkillForge NEVER
# auto-executes them.
# ----------------------------------------------------------------------------


_DESIGN_PROMPT = """# Design prompt — {skill}

Use this prompt with an AI assistant when designing this skill's domain.

> Help me design a {{skill}} system using {primary}. Include the data model,
> key interfaces, error-handling strategy, and how the recommended workflow maps
> to concrete modules. Call out any architectural risks.
"""


_IMPLEMENT_PROMPT = """# Implementation prompt — {skill}

Use this prompt when scaffolding implementation files.

> Generate starter implementation for {primary} and {secondary} following the
> {skill} workflow. Include module boundaries, typing, basic error handling,
> and TODO markers for parts that need project-specific decisions. Do NOT run
> any commands; just produce the files.
"""


_TEST_PROMPT = """# Testing prompt — {skill}

Use this prompt to generate a test plan and starter tests.

> Produce a test plan for a {primary} project following the {skill} skill.
> Cover unit, integration, and (where relevant) end-to-end tests. Then generate
> starter tests using the recommended testing tools.
"""


_PY_SERVICE = '''"""Service layer scaffold for {{ skill.title }}.

Keep business logic here, independent of the framework and the database.
"""
from __future__ import annotations

from typing import Protocol


class Repository(Protocol):
    """Persistence interface implemented by the repository layer."""
    # TODO: define the methods your service needs.
    pass


class {{ skill.name | replace("-", "_") | capitalize }}Service:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    # TODO: implement domain operations.
    pass
'''


_PY_REPOSITORY = '''"""Repository layer scaffold for {{ skill.title }}.

Encapsulates persistence so the service layer stays framework-agnostic.
"""
from __future__ import annotations

from typing import Any


class {{ skill.name | replace("-", "_") | capitalize }}Repository:
    def __init__(self, session: Any) -> None:
        self._session = session

    # TODO: implement CRUD + domain-specific queries.
    pass
'''


_FASTAPI_ROUTER = '''"""FastAPI router scaffold for {{ skill.title }}."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/v1/{{ skill.name }}", tags=["{{ skill.name }}"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# TODO: add endpoints that delegate to the service layer.
'''


_GO_HANDLER = '''// Handler scaffold for {{ skill.title }}.
package handler

import (
	"encoding/json"
	"net/http"
)

// HealthHandler is a reference handler. Replace with your real handlers.
func HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
'''


_TS_COMPONENT = '''// Reference component scaffold for {{ skill.title }}.
import * as React from "react";

export interface {{ skill.name | pascal_case }}Props {
  // TODO: define props.
}

export function {{ skill.name | pascal_case }}(props: {{ skill.name | pascal_case }}Props) {
  return (
    <section>
      <h1>{{ skill.title }}</h1>
      {/* TODO: implement. */}
    </section>
  );
}
'''


_PIPELINE = '''"""Pipeline scaffold for {{ skill.title }}.

Reference only — adapt to Airflow or Dagster idioms.
"""
from __future__ import annotations


def extract() -> None:
    """TODO: pull source data."""
    pass


def transform() -> None:
    """TODO: apply transformations (e.g. dbt)."""
    pass


def load() -> None:
    """TODO: write to the warehouse."""
    pass


def run() -> None:
    extract()
    transform()
    load()


if __name__ == "__main__":
    run()
'''


_DBT_MODEL = '''-- dbt model scaffold for {{ skill.title }}.
-- Reference only. Replace with your actual model logic.
with source as (
    select * from {{ ref("stg_source") }}
),
final as (
    select
        id,
        created_at,
        -- TODO: add transformations
    from source
)
select * from final
'''


_TERRAFORM = '''# Terraform scaffold for {{ skill.title }}.
# Reference only — adjust providers and resources to your environment.

terraform {
  required_version = ">= 1.5.0"
}

# TODO: configure providers and resources for {{ skill.title }}.
'''


_DOCKERFILE = '''# Dockerfile scaffold for {{ skill.title }}.
# Reference only.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "-m", "your_app"]
'''


_RAG_CHAIN = '''"""RAG chain scaffold for {{ skill.title }}.

Reference only — wire up your chosen vector store and LLM provider.
"""
from __future__ import annotations


def build_chain():
    # TODO: implement retrieval + generation using LangChain/LlamaIndex.
    raise NotImplementedError


def answer(question: str) -> str:
    chain = build_chain()
    return chain.invoke(question)
'''


_CONFIG_EXAMPLE = '''# Example configuration for {{ skill.title }}.
# Copy to config.local.yaml and fill in values. Never commit secrets.
environment: "{{ skill.name }}"
# TODO: add environment variables and feature flags for your project.
'''


_SCRIPTS_README = """# Scripts — {skill}

This directory is a **reference only**. SkillForge **never auto-executes** any
script here. Review every script carefully before running it locally.

The scripts you add should reflect the recommended tools: {tools}.

## Conventions

- Each script should be idempotent where possible.
- Document prerequisites and side effects at the top of every script.
- Prefer scripts that fail loudly over scripts that swallow errors.
"""


# ----------------------------------------------------------------------------
# Small Jinja-like helpers for the embedded scaffolds above.
#
# The scaffolds above use ``{{ ... }}`` syntax but are rendered as plain
# strings by the installer (they are *output* files for the installed skill,
# not templates SkillForge renders now). We only need a slug/pascal helper for
# the example TypeScript scaffold when generating it.
# ----------------------------------------------------------------------------


_PASCAL_RE = re.compile(r"[^A-Za-z0-9]+")


def _slug(text: str) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "skill"


def _pascal(text: str) -> str:
    parts = [p for p in _PASCAL_RE.split(text or "") if p]
    return "".join(p.capitalize() for p in parts) or "Skill"


def pascal_case(text: str) -> str:
    """PascalCase helper; exposed for users who re-render the ``templates/*.j2`` scaffolds later."""
    return _pascal(text)
