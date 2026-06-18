"""SkillForge CLI — Typer + Rich.

Commands:

    skillforge serve
    skillforge plan "<message>"
    skillforge generate --manifest ./config.yaml --out ./generated-skill
    skillforge install ./generated-skill [--overwrite]
    skillforge list
    skillforge validate ./generated-skill
    skillforge remove <skill-name>

The CLI reuses the same service layer as the FastAPI API, so behavior is
identical between the Web UI and the command line.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Import the shared backend service layer. The CLI depends on skillforge-api.
from skillforge_api.schemas.manifest import (
    Architecture,
    Outputs,
    Safety,
    SkillAI,
    SkillManifest,
    SkillMeta,
    Tool,
)
from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_generator import SkillGenerator
from skillforge_api.services.skill_installer import InstallerError, SkillInstaller
from skillforge_api.services.skill_registry import SkillRegistry
from skillforge_api.services.skill_validator import SkillValidator
from skillforge_api.settings import get_settings

console = Console()

app = typer.Typer(
    name="skillforge",
    help="AI-powered local skill builder for engineers.",
    no_args_is_help=True,
    add_completion=False,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _print_manifest(manifest: SkillManifest, explanation: str | None = None) -> None:
    if explanation:
        console.print(Panel(explanation, title="AI Recommendation", border_style="cyan"))

    table = Table(title=f"Skill: {manifest.skill.name}", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Name", manifest.skill.name)
    table.add_row("Title", manifest.skill.title)
    table.add_row("Domain", manifest.skill.domain)
    table.add_row("Description", manifest.skill.description)
    table.add_row("Version", manifest.skill.version)
    console.print(table)

    tools = Table(title="Recommended Tools", show_header=True, header_style="bold green")
    tools.add_column("Tool")
    tools.add_column("Category")
    tools.add_column("Reason")
    for t in manifest.tools:
        tools.add_row(t.name, t.category, t.reason)
    console.print(tools)


def _load_manifest_from_config(path: Path) -> SkillManifest:
    """Reconstruct a :class:`SkillManifest` from a generated ``config.yaml``."""
    if not path.is_file():
        raise typer.BadParameter(f"Manifest file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter(f"{path} is not a valid skill config mapping.")

    skill_raw = raw.get("skill") or {}
    tools = [
        Tool(
            name=t.get("name", ""),
            category=t.get("category", "misc"),
            enabled=bool(t.get("enabled", True)),
            reason=t.get("reason", ""),
        )
        for t in (raw.get("tools") or [])
    ]
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
            status=str(skill_raw.get("status", "draft")),
        ),
        ai=SkillAI(
            generated_by=str(ai.get("generated_by", "skillforge")),
            planner_model=str(ai.get("planner_model", "")),
        ),
        tools=tools,
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


def _write_generated(out_dir: Path, files) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        target = out_dir / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content, encoding="utf-8")


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------


def _find_web_dir() -> Path | None:
    """Locate the exported Web UI directory.

    Delegates to :func:`skillforge_api.paths.web_export_dir`, which handles both
    the normal repo layout and the PyInstaller frozen layout (``sys._MEIPASS``).
    Honors ``$SKILLFORGE_WEB_DIR`` as an explicit override.
    """
    from skillforge_api.paths import web_export_dir

    return web_export_dir()


def _run_web_build() -> tuple[bool, str]:
    """Build the Web UI export (``npm run build`` in apps/web). Returns (ok, note)."""
    import shutil
    import subprocess

    npm = shutil.which("npm")
    if not npm:
        return False, "npm not found on PATH; install Node.js to build the Web UI."

    here = Path(__file__).resolve()
    apps_dir = here.parents[2] if len(here.parents) > 2 else None
    web_dir = apps_dir / "web" if apps_dir and apps_dir.name == "apps" else None
    if web_dir is None or not (web_dir / "package.json").is_file():
        web_dir = Path.cwd() / "apps" / "web"
    if not (web_dir / "package.json").is_file():
        return False, f"could not locate apps/web near {web_dir}"

    console.print(f"[dim]Building Web UI in {web_dir} …[/dim]")
    try:
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=web_dir, check=True)
        subprocess.run([npm, "run", "build"], cwd=web_dir, check=True)
    except subprocess.CalledProcessError as exc:
        return False, f"Web UI build failed: {exc}"
    return True, ""


def _spawn_dev_web() -> tuple[Any, int]:
    """Spawn ``npm run dev`` in apps/web; return (proc, port)."""
    import shutil
    import subprocess

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm not found; install Node.js to use --dev mode.")

    here = Path(__file__).resolve()
    apps_dir = here.parents[2] if len(here.parents) > 2 else None
    web_dir = apps_dir / "web" if apps_dir and apps_dir.name == "apps" else Path.cwd() / "apps" / "web"
    port = 3000
    env = dict(os.environ)
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=web_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, port


@app.command()
def serve(
    host: str = typer.Option(None, "--host", help="Bind host. Defaults to SKILLFORGE_API_HOST."),
    port: int = typer.Option(None, "--port", "-p", help="Bind port. Defaults to SKILLFORGE_API_PORT."),
    dev: bool = typer.Option(
        False,
        "--dev",
        help="Run the Next.js dev server (:3000) alongside the API (:8000) for hot-reload.",
    ),
    api_only: bool = typer.Option(
        False,
        "--api-only",
        help="Serve the API only; do not mount the bundled Web UI.",
    ),
    build_web: bool = typer.Option(
        False,
        "--build-web",
        help="Build (or refresh) the Web UI export before serving in bundled mode.",
    ),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn auto-reload (dev)."),
) -> None:
    """Start SkillForge.

    By default this serves BOTH the API and the bundled Web UI from one port
    (the "single binary" experience): open http://localhost:8000 and you get
    the full app — no second terminal, no CORS, no Node runtime.

    Modes:
      * default        — API + bundled Web UI on one port.
      * --build-web    — same, but rebuild the Web UI export first.
      * --dev          — API on :8000 + Next dev server on :3000 (hot-reload).
      * --api-only     — API only (headless / testing).
    """
    import uvicorn

    from skillforge_api.logging_config import build_log_config

    settings = get_settings()
    host = host or settings.api_host
    port = port or settings.api_port

    # One unified logging format for uvicorn access logs, httpx outbound
    # requests, and app code. Passing this to uvicorn's log_config replaces
    # uvicorn's default "INFO:     <addr> - ..." format so every line matches.
    log_config = build_log_config()

    console.print(Panel.fit(
        f"AI provider : {settings.ai_provider}  (model: {settings.model})\n"
        f"Skills dir  : {settings.skills_dir}",
        title="[bold cyan]SkillForge[/bold cyan]",
        border_style="cyan",
    ))

    if dev:
        _serve_dev(host, port)
        return

    if api_only:
        console.print(f"[bold]API-only[/bold] on http://{host}:{port}  (OpenAPI: /docs)")
        uvicorn.run("skillforge_api.main:app", host=host, port=port, reload=reload, log_config=log_config)
        return

    # Bundled mode: ensure the Web UI export exists, optionally rebuild it.
    web_dir = _find_web_dir()
    if web_dir is None or build_web:
        ok, note = _run_web_build()
        if not ok:
            console.print(f"[yellow]Web UI not available:[/yellow] {note}")
            console.print(
                "[yellow]Continuing in API-only mode. Open /docs, or build the UI with "
                "`npm run build` in apps/web.[/yellow]"
            )
            web_dir = None
        else:
            web_dir = _find_web_dir()

    # When a Web UI dir is available, run uvicorn against a factory that mounts
    # it; otherwise fall back to the plain API app.
    if web_dir:
        console.print(
            f"[bold green]Serving API + Web UI[/bold green] on http://{host}:{port}  "
            f"(Web UI from {web_dir})"
        )

        # uvicorn can't easily take constructor args for the app, so we build the
        # app object here and point uvicorn at it (no reload in bundled mode).
        from skillforge_api.main import create_app

        app = create_app(static_dir=str(web_dir))
        uvicorn.run(app, host=host, port=port, reload=False, log_config=log_config)
    else:
        console.print(f"[bold]API-only[/bold] on http://{host}:{port}  (OpenAPI: /docs)")
        uvicorn.run("skillforge_api.main:app", host=host, port=port, reload=reload, log_config=log_config)


def _serve_dev(host: str, port: int) -> None:
    """Run the API on *port* and the Next dev server on :3000 in parallel."""
    import signal
    import threading
    import uvicorn

    web_proc = None
    try:
        web_proc, web_port = _spawn_dev_web()
        console.print(
            f"[bold]Dev mode:[/bold] API on http://{host}:{port}  ·  "
            f"Web UI (hot-reload) on http://localhost:{web_port}"
        )
        console.print(
            "[dim]The dev server proxies /api and /health to the API, so just open "
            f"http://localhost:{web_port}. Ctrl-C stops both.[/dim]"
        )

        # Forward Ctrl-C / SIGTERM to the child, then run uvicorn in-process.
        def _stop_web(*_):
            if web_proc and web_proc.poll() is None:
                web_proc.terminate()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _stop_web)

        config = uvicorn.Config("skillforge_api.main:app", host=host, port=port, reload=True)
        config.log_config = build_log_config()
        server = uvicorn.Server(config)
        server.run()
    except RuntimeError as exc:
        console.print(f"[yellow]Could not start dev web server:[/yellow] {exc}")
        console.print(f"[yellow]Falling back to API-only on http://{host}:{port}[/yellow]")
        uvicorn.run("skillforge_api.main:app", host=host, port=port, reload=True, log_config=build_log_config())
    finally:
        if web_proc and web_proc.poll() is None:
            web_proc.terminate()


@app.command()
def plan(
    message: str = typer.Argument(..., help="Natural-language engineering need."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write the generated config.yaml to this path."
    ),
) -> None:
    """Plan a skill from a natural-language message using AI."""
    try:
        manifest, explanation = AISkillPlanner().plan(message)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    _print_manifest(manifest, explanation)

    if output:
        # Generate config.yaml so the output is directly usable by `generate`.
        config_text = SkillGenerator()._config_yaml(manifest)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(config_text, encoding="utf-8")
        console.print(f"\n[green]Wrote manifest to[/green] {output}")


@app.command()
def generate(
    manifest: Path = typer.Option(..., "--manifest", "-m", help="Path to a config.yaml manifest."),
    out: Path = typer.Option(Path("./generated-skill"), "--out", "-o", help="Output directory."),
) -> None:
    """Generate skill files from a manifest config.yaml."""
    parsed = _load_manifest_from_config(manifest)
    files = SkillGenerator().generate(parsed)
    _write_generated(out, files)
    console.print(f"[green]Generated[/green] {len(files)} files in [bold]{out}[/bold]")
    for f in sorted(files, key=lambda x: x.path):
        console.print(f"  • {f.path}")


@app.command()
def install(
    path: Path = typer.Argument(..., help="Skill directory (must contain config.yaml) or a config.yaml."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing install."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Install a generated skill into the local skills directory."""
    config_path = path / "config.yaml" if path.is_dir() else path
    parsed = _load_manifest_from_config(config_path)

    if not yes:
        confirm = typer.confirm(
            f"Install skill '{parsed.skill.name}' into {get_settings().skills_dir}?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(1)

    try:
        outcome = SkillInstaller().install(parsed, overwrite=overwrite)
    except InstallerError as exc:
        console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(1)

    if outcome.skipped_existing:
        console.print(
            f"[yellow]A skill named '{parsed.skill.name}' already exists at[/yellow] {outcome.path}\n"
            f"Re-run with --overwrite to replace it."
        )
        raise typer.Exit(2)

    console.print(f"[green bold]Installed[/green bold] {parsed.skill.name} → {outcome.path}")


@app.command(name="list")
def list_skills() -> None:
    """List installed skills."""
    skills = SkillRegistry().list_installed()
    if not skills:
        console.print("[dim]No skills installed yet.[/dim]")
        return
    table = Table(title="Installed Skills", show_header=True, header_style="bold magenta")
    table.add_column("Name")
    table.add_column("Domain")
    table.add_column("Version")
    table.add_column("Path")
    for s in skills:
        table.add_row(s.name, s.domain, s.version, s.path)
    console.print(table)


@app.command()
def validate(
    path: Path = typer.Argument(..., help="Skill directory to validate."),
) -> None:
    """Validate a generated or installed skill directory."""
    result = SkillValidator().validate_directory(path)
    if result.valid:
        console.print(f"[green bold]✓ Valid:[/green bold] {path}")
        for w in result.issues:
            console.print(f"  [yellow]warning:[/yellow] {w.message}")
        return
    console.print(f"[red bold]✗ Invalid:[/red bold] {path}")
    for issue in result.errors:
        console.print(f"  [red]{issue.code}:[/red] {issue.message}")
    raise typer.Exit(1)


@app.command()
def remove(
    skill_name: str = typer.Argument(..., help="Name of the installed skill to remove."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Remove an installed skill by name."""
    if not yes:
        confirm = typer.confirm(f"Remove skill '{skill_name}'?", default=False)
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(1)
    removed = SkillRegistry().remove(skill_name)
    if not removed:
        console.print(f"[red]No installed skill named '{skill_name}'.[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Removed[/green] {skill_name}")


@app.command()
def config() -> None:
    """Show the current SkillForge configuration (secrets are masked)."""
    s = get_settings()
    table = Table(title="SkillForge Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting")
    table.add_column("Value")
    table.add_row("ai_provider", s.ai_provider)
    table.add_row("model", s.model)
    table.add_row("openai_base_url", s.openai_base_url)
    table.add_row("openai_api_key", "***" if s.openai_api_key else "(unset)")
    table.add_row("ollama_base_url", s.ollama_base_url)
    table.add_row("anthropic_base_url", getattr(s, "anthropic_base_url", "https://api.anthropic.com"))
    table.add_row("anthropic_api_key", "***" if getattr(s, "anthropic_api_key", "") else "(unset)")
    table.add_row("gemini_base_url", getattr(s, "gemini_base_url", "https://generativelanguage.googleapis.com"))
    table.add_row("gemini_api_key", "***" if getattr(s, "gemini_api_key", "") else "(unset)")
    table.add_row("cohere_base_url", getattr(s, "cohere_base_url", "https://api.cohere.com"))
    table.add_row("cohere_api_key", "***" if getattr(s, "cohere_api_key", "") else "(unset)")
    table.add_row("skills_dir", str(s.skills_dir))
    table.add_row("db_path", str(s.db_path))
    table.add_row("api_host", s.api_host)
    table.add_row("api_port", str(s.api_port))
    table.add_row("eval_max_calls", str(getattr(s, "eval_max_calls", 50)))
    console.print(table)


if __name__ == "__main__":  # pragma: no cover
    app()
