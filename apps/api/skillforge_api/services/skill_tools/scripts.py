"""Real, runnable script/config/CLI/MCP content for each tool.

Every entry here is a REAL file — not a stub. `dev_server.py` actually launches
uvicorn; `migrate.sh` actually runs `alembic upgrade head`; `ci.yml` is a valid
GitHub Actions workflow. Contributors add entries here to teach SkillForge new
tool-specific artifacts.
"""

from __future__ import annotations

# Each script is keyed by a stable id. The registry maps tool names → these ids.
SCRIPTS: dict[str, str] = {}


def _register(script_id: str, content: str) -> None:
    SCRIPTS[script_id] = content


# ============================================================================
# FastAPI
# ============================================================================

_register("fastapi/dev_server.py", '''#!/usr/bin/env python3
"""Launch the FastAPI dev server (uvicorn with hot reload).

Usage: python tools/dev_server.py [--port 8000]
"""
import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="FastAPI dev server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--reload", action="store_true", default=True)
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    # Adjust 'app.main:app' to your project's module path.
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
''')

_register("fastapi/new_endpoint.py", '#!/usr/bin/env python3\n'
    '# Scaffold a new FastAPI router file with a CRUD-shaped endpoint.\n'
    '# Usage: python tools/new_endpoint.py products\n'
    '# Creates: app/routers/products.py\n'
    'import sys\n'
    'from pathlib import Path\n\n'
    '# The template uses {name} placeholders; double-brace for .format() literals.\n'
    'TEMPLATE = (\n'
    '    \'"""Router for {name}."""\\n\'\n'
    '    \'from fastapi import APIRouter\\n\\n\'\n'
    '    \'router = APIRouter(prefix="/api/v1/{name}", tags=["{name}"])\\n\\n\\n\'\n'
    '    \'@router.get("/")\\n\'\n'
    '    \'async def list_{name}() -> dict:\\n\'\n'
    '    \'    return {{"items": []}}\\n\\n\\n\'\n'
    '    \'@router.post("/")\\n\'\n'
    '    \'async def create_{name}() -> dict:\\n\'\n'
    '    \'    return {{"created": True}}\\n\\n\\n\'\n'
    '    \'@router.get("/{item_id}")\\n\'\n'
    '    \'async def get_{name}(item_id: str) -> dict:\\n\'\n'
    '    \'    return {{"id": item_id}}\\n\'\n'
    ')\n\n\n'
    'def main() -> None:\n'
    '    if len(sys.argv) < 2:\n'
    '        print("Usage: python tools/new_endpoint.py <resource-name>", file=sys.stderr)\n'
    '        sys.exit(1)\n'
    '    name = sys.argv[1].strip("-").replace("-", "_")\n'
    '    out = Path("app/routers") / f"{name}.py"\n'
    '    out.parent.mkdir(parents=True, exist_ok=True)\n'
    '    out.write_text(TEMPLATE.format(name=name))\n'
    '    print(f"Created {out}")\n\n\n'
    'if __name__ == "__main__":\n'
    '    main()\n')

# ============================================================================
# SQLAlchemy / Alembic
# ============================================================================

_register("alembic/migrate.sh", '''#!/usr/bin/env bash
# Run database migrations (alembic upgrade head).
# Usage: bash tools/migrate.sh
set -euo pipefail
if ! command -v alembic &>/dev/null; then
  echo "alembic not installed. Run: pip install alembic" >&2
  exit 1
fi
alembic upgrade head
echo "Migrations applied."
''')

_register("alembic/new_migration.sh", '''#!/usr/bin/env bash
# Create a new Alembic migration.
# Usage: bash tools/new_migration.sh "add users table"
set -euo pipefail
MSG="${1:-auto migration}"
alembic revision --autogenerate -m "$MSG"
echo "Migration created. Review it, then run: bash tools/migrate.sh"
''')

_register("alembic/alembic.ini", '''[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
''')

# ============================================================================
# Pytest
# ============================================================================

_register("pytest/test.sh", '''#!/usr/bin/env bash
# Run the test suite.
# Usage: bash tools/test.sh [--verbose]
set -euo pipefail
ARGS="${*:--q}"
pytest $ARGS
''')

_register("pytest/conftest.py", '''"""Shared pytest fixtures."""
import pytest


@pytest.fixture
def app():
    """Return the app instance for testing. Adjust the import to your project."""
    # from app.main import app
    # return app
    pytest.skip("Configure this fixture to import your app")
''')

# ============================================================================
# Docker
# ============================================================================

_register("docker/docker_build.sh", '''#!/usr/bin/env bash
# Build the Docker image.
# Usage: bash tools/docker_build.sh [image-name]
set -euo pipefail
IMAGE="${1:-$(basename "$PWD")}"
docker build -t "$IMAGE" .
echo "Built $IMAGE"
''')

_register("docker/docker_run.sh", '''#!/usr/bin/env bash
# Run the Docker container.
# Usage: bash tools/docker_run.sh [image-name]
set -euo pipefail
IMAGE="${1:-$(basename "$PWD")}"
docker run --rm -p 8000:8000 "$IMAGE"
''')

_register("docker/Dockerfile", '''# Dockerfile generated by SkillForge.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
''')

# ============================================================================
# GitHub Actions CI
# ============================================================================

_register("cicd/ci.yml", '''name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -e ".[dev]" || pip install -r requirements.txt
      - name: Lint
        run: ruff check . || true
      - name: Test
        run: pytest -q
''')

# ============================================================================
# Stack configs (pyproject.toml, requirements.txt, .env.example)
# ============================================================================

_register("config/pyproject.toml", '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{ skill_name }}"
version = "{{ version }}"
description = "{{ description }}"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.4",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
testpaths = ["tests"]
''')

_register("config/requirements.txt", '''fastapi>=0.110
uvicorn[standard]>=0.27
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.6
# dev
pytest>=8.0
httpx>=0.27
ruff>=0.4
''')

_register("config/.env.example", '''# Environment configuration. Copy to .env and fill in values.
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
SECRET_KEY=change-me
DEBUG=true
''')

# ============================================================================
# dbt
# ============================================================================

_register("dbt/run_dbt.sh", '''#!/usr/bin/env bash
# Run dbt models.
# Usage: bash tools/run_dbt.sh
set -euo pipefail
dbt run --profiles-dir .
echo "dbt models built."
''')

_register("dbt/test_dbt.sh", '''#!/usr/bin/env bash
# Run dbt tests.
set -euo pipefail
dbt test --profiles-dir .
echo "dbt tests passed."
''')

_register("dbt/dbt_project.yml", '''name: "{{ skill_name }}"
version: "1.0.0"
config-version: 2
profile: "default"

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]

models:
  {{ skill_name }}:
    +materialized: table
''')

# ============================================================================
# Next.js
# ============================================================================

_register("nextjs/dev.sh", '''#!/usr/bin/env bash
# Start the Next.js dev server.
# Usage: bash tools/dev.sh
set -euo pipefail
npm run dev
''')

_register("nextjs/new_page.tsx", '''#!/usr/bin/env node
/** Scaffold a new Next.js App-Router page.
 * Usage: node tools/new_page.tsx about
 * Creates: app/about/page.tsx
 */
import { writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";

const name = process.argv[2];
if (!name) {
  console.error("Usage: node tools/new_page.tsx <page-name>");
  process.exit(1);
}

const path = `app/${name}/page.tsx`;
mkdirSync(dirname(path), { recursive: true });
writeFileSync(
  path,
  `export default function ${name.charAt(0).toUpperCase() + name.slice(1)}Page() {\\n  return <main>${name}</main>;\\n}\\n`,
);
console.log(`Created ${path}`);
''')

# ============================================================================
# Playwright
# ============================================================================

_register("playwright/e2e.sh", '''#!/usr/bin/env bash
# Run Playwright e2e tests.
# Usage: bash tools/e2e.sh
set -euo pipefail
npx playwright test
''')

# ============================================================================
# Skill-as-CLI (Makefile + cli.py)
# ============================================================================

_register("cli/Makefile", '''# SkillForge-generated CLI for {{ skill_name }}.
# Usage: make <target>

.PHONY: help dev test migrate docker-up docker-build new-api

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "\\033[36m%-15s\\033[0m %s\\n", $$1, $$2}'

{{ cli_targets }}
''')

_register("cli/cli.py", '''#!/usr/bin/env python3
"""Skill CLI — exposes the skill's helper scripts as sub-commands.

Usage: python tools/cli.py <command>
Generated by SkillForge. Edit freely.
"""
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).parent

# Map command names to script paths.
COMMANDS = {
{{ cli_command_map }}
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python tools/cli.py <{'|'.join(COMMANDS)}>", file=sys.stderr)
        sys.exit(1)
    script = TOOLS / COMMANDS[sys.argv[1]]
    if not script.exists():
        print(f"Script not found: {script}", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run([sys.executable, str(script), *sys.argv[2:]])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
''')

# ============================================================================
# MCP / agent tool wrappers
# ============================================================================

_register("mcp/mcp_server.py", '''#!/usr/bin/env python3
"""MCP server exposing this skill's helpers as callable tools for an AI agent.

This is a reference implementation using the Model Context Protocol (MCP).
Install the SDK: pip install mcp
Run: python tools/mcp_server.py

The agent can then call list_tools(), run_tests(), etc. as function calls.
"""
from __future__ import annotations

# MCP is optional — the server only starts if the SDK is installed.
try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("{{ skill_name }}")

    @mcp.tool()
    def list_tools() -> list[str]:
        """List the tools/helper-scripts available in this skill."""
        return [
{{ mcp_tool_list }}
        ]

    @mcp.tool()
    def run_tests() -> str:
        """Run the skill's test suite."""
        import subprocess
        result = subprocess.run(
            ["bash", str(__import__("pathlib").Path(__file__).parent / "test.sh")],
            capture_output=True, text=True, timeout=120,
        )
        return result.stdout + result.stderr

    if __name__ == "__main__":
        mcp.run()
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=__import__("sys").stderr)
''')
