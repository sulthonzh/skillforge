"""ToolArtifactRegistry — maps each catalog tool to the artifacts it contributes.

The generator calls ``registry.artifacts_for(manifest)`` to get the list of
files to emit under the skill's ``tools/`` directory (+ stack config files).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...schemas.manifest import SkillManifest
from .scripts import SCRIPTS


@dataclass(frozen=True)
class Artifact:
    """A single generated file."""

    path: str  # relative to the skill dir, e.g. "tools/dev_server.py"
    script_id: str  # key into SCRIPTS
    executable: bool = False  # chmod +x?
    cli_command: str | None = None  # name exposed in the CLI/Makefile, if any


# Each tool (lowercase) → list of (script_id, target_path, executable, cli_cmd).
# The registry merges these for all tools in a manifest.
_TOOL_ARTIFACTS: dict[str, list[Artifact]] = {
    "fastapi": [
        Artifact("tools/dev_server.py", "fastapi/dev_server.py", executable=True, cli_command="dev"),
        Artifact("tools/new_endpoint.py", "fastapi/new_endpoint.py", executable=True, cli_command="new-api"),
        Artifact("config/pyproject.toml", "config/pyproject.toml"),
        Artifact("config/requirements.txt", "config/requirements.txt"),
        Artifact("config/.env.example", "config/.env.example"),
        Artifact("Dockerfile", "docker/Dockerfile"),
    ],
    "sqlalchemy": [
        Artifact("tools/migrate.sh", "alembic/migrate.sh", executable=True, cli_command="migrate"),
        Artifact("tools/new_migration.sh", "alembic/new_migration.sh", executable=True, cli_command="new-migration"),
        Artifact("alembic.ini", "alembic/alembic.ini"),
    ],
    "alembic": [
        Artifact("tools/migrate.sh", "alembic/migrate.sh", executable=True, cli_command="migrate"),
        Artifact("tools/new_migration.sh", "alembic/new_migration.sh", executable=True, cli_command="new-migration"),
        Artifact("alembic.ini", "alembic/alembic.ini"),
    ],
    "pytest": [
        Artifact("tools/test.sh", "pytest/test.sh", executable=True, cli_command="test"),
        Artifact("tests/conftest.py", "pytest/conftest.py"),
    ],
    "docker": [
        Artifact("tools/docker_build.sh", "docker/docker_build.sh", executable=True, cli_command="docker-build"),
        Artifact("tools/docker_run.sh", "docker/docker_run.sh", executable=True, cli_command="docker-up"),
        Artifact("Dockerfile", "docker/Dockerfile"),
    ],
    "github actions": [
        Artifact(".github/workflows/ci.yml", "cicd/ci.yml", cli_command="ci-check"),
    ],
    "dbt": [
        Artifact("tools/run_dbt.sh", "dbt/run_dbt.sh", executable=True, cli_command="dbt-run"),
        Artifact("tools/test_dbt.sh", "dbt/test_dbt.sh", executable=True, cli_command="dbt-test"),
        Artifact("dbt_project.yml", "dbt/dbt_project.yml"),
    ],
    "next.js": [
        Artifact("tools/dev.sh", "nextjs/dev.sh", executable=True, cli_command="dev"),
        Artifact("tools/new_page.tsx", "nextjs/new_page.tsx", executable=True, cli_command="new-page"),
    ],
    "playwright": [
        Artifact("tools/e2e.sh", "playwright/e2e.sh", executable=True, cli_command="e2e"),
    ],
}


class ToolArtifactRegistry:
    """Resolve which artifacts to emit for a given manifest."""

    def artifacts_for(self, manifest: SkillManifest) -> list[Artifact]:
        """Return the deduplicated artifact list for the manifest's tools."""
        tools = {t.name.lower() for t in (manifest.enabled_tools or manifest.tools)}
        seen_paths: set[str] = set()
        result: list[Artifact] = []
        for tool_name, artifacts in _TOOL_ARTIFACTS.items():
            if tool_name in tools:
                for art in artifacts:
                    if art.path not in seen_paths:
                        seen_paths.add(art.path)
                        result.append(art)
        return result

    def render_artifact(self, art: Artifact, manifest: SkillManifest) -> str:
        """Render the artifact's content, substituting manifest placeholders."""
        content = SCRIPTS.get(art.script_id, "")
        # Simple Jinja-like placeholder substitution (avoid Jinja for raw scripts).
        replacements = {
            "{{ skill_name }}": manifest.skill.name,
            "{{ version }}": manifest.skill.version,
            "{{ description }}": manifest.skill.description,
        }
        for token, value in replacements.items():
            content = content.replace(token, value)
        return content

    def has_tools(self, manifest: SkillManifest) -> bool:
        return len(self.artifacts_for(manifest)) > 0

    def cli_targets(self, manifest: SkillManifest) -> str:
        """Render the Makefile target lines for the manifest's CLI commands."""
        artifacts = self.artifacts_for(manifest)
        lines: list[str] = []
        for art in artifacts:
            if art.cli_command:
                script = art.path.replace("tools/", "")
                lines.append(f'{art.cli_command}: ## {art.cli_command}\\n\tbash {art.path} "$@"')
        return "\n\n".join(lines)

    def cli_command_map(self, manifest: SkillManifest) -> str:
        """Render the Python dict entries for cli.py's COMMANDS."""
        artifacts = self.artifacts_for(manifest)
        lines: list[str] = []
        for art in artifacts:
            if art.cli_command:
                rel = art.path.replace("tools/", "")
                lines.append(f'    "{art.cli_command}": "{rel}",')
        return "\n".join(lines)

    def mcp_tool_list(self, manifest: SkillManifest) -> str:
        """Render the MCP tool list (names of CLI commands)."""
        artifacts = self.artifacts_for(manifest)
        names = [art.cli_command for art in artifacts if art.cli_command]
        if not names:
            return '        "run_tests",'
        return "\n".join(f'        "{n}",' for n in names)


_registry: ToolArtifactRegistry | None = None


def get_registry() -> ToolArtifactRegistry:
    global _registry
    if _registry is None:
        _registry = ToolArtifactRegistry()
    return _registry
