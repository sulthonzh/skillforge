"""Safe opt-in executor for generated skill tools.

Lets a user run a generated helper script from the UI with strong guardrails:
  - Only scripts under the skill's ``tools/`` directory are runnable (allowlist).
  - Execution requires explicit ``confirm=True``.
  - Preview-first: dry-run returns the exact command without executing.
  - Bounded timeout (default 30s).
  - Full audit log at ``~/.skillforge/exec_log.jsonl``.
  - ``safety.auto_execute_scripts`` stays false; this is opt-in per action.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ...settings import get_settings
from ..skill_registry import SkillRegistry

DEFAULT_TIMEOUT = 30
# Only these script names (relative to tools/) are runnable. The allowlist is
# explicit so a malicious manifest can't inject an arbitrary executable.
_RUNNABLE_SCRIPTS = frozenset(
    {
        "dev_server.py",
        "new_endpoint.py",
        "migrate.sh",
        "new_migration.sh",
        "test.sh",
        "docker_build.sh",
        "docker_run.sh",
        "run_dbt.sh",
        "test_dbt.sh",
        "dev.sh",
        "new_page.tsx",
        "e2e.sh",
        "cli.py",
    }
)


class ExecutorError(RuntimeError):
    """Raised when a run cannot proceed safely."""


@dataclass
class RunPreview:
    script: str
    command: list[str]
    cwd: str
    runnable: bool
    reason: str = ""


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    command: list[str]
    cwd: str


class ToolExecutor:
    """Preview and run generated skill tools with guardrails."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    def preview(self, skill_name: str, script: str) -> RunPreview:
        """Dry-run: return what would execute without running it."""
        script = self._safe_script_name(script)
        record = SkillRegistry().get(skill_name)
        if record is None:
            raise ExecutorError(f"No installed skill named {skill_name!r}")
        skill_dir = Path(record.path)
        script_path = skill_dir / "tools" / script
        runnable = script in _RUNNABLE_SCRIPTS and script_path.is_file()
        command = self._build_command(script, script_path)
        reason = ""
        if not script_path.is_file():
            reason = f"Script not found at tools/{script}"
        elif script not in _RUNNABLE_SCRIPTS:
            reason = f"Script {script!r} is not in the runnable allowlist"
        return RunPreview(
            script=script,
            command=command,
            cwd=str(skill_dir),
            runnable=runnable,
            reason=reason,
        )

    def run(self, skill_name: str, script: str, confirm: bool, args: str = "") -> RunResult:
        """Execute a generated tool. Requires ``confirm=True``."""
        if not confirm:
            raise ExecutorError("Execution requires explicit confirmation (confirm=True).")
        prev = self.preview(skill_name, script)
        if not prev.runnable:
            raise ExecutorError(f"Not runnable: {prev.reason}")

        command = prev.command[:]
        if args:
            command.extend(shlex.split(args))

        self._audit_log(skill_name, script, args, "start")
        try:
            proc = subprocess.run(
                command,
                cwd=prev.cwd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env={**os.environ},
            )
            result = RunResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                timed_out=False,
                command=command,
                cwd=prev.cwd,
            )
            self._audit_log(skill_name, script, args, "done", proc.returncode)
            return result
        except subprocess.TimeoutExpired:
            self._audit_log(skill_name, script, args, "timeout", -1)
            return RunResult(
                exit_code=-1,
                stdout="",
                stderr=f"Timed out after {self._timeout}s",
                timed_out=True,
                command=command,
                cwd=prev.cwd,
            )

    # ---- helpers ----
    def _safe_script_name(self, script: str) -> str:
        """Sanitize: only a bare filename, no path separators."""
        name = Path(script).name  # strip any dir components
        if "/" in script or "\\" in script or ".." in script:
            raise ExecutorError(f"Unsafe script name: {script!r}")
        return name

    def _build_command(self, script: str, script_path: Path) -> list[str]:
        if script.endswith(".py"):
            import sys
            return [sys.executable, str(script_path)]
        if script.endswith(".sh"):
            return ["bash", str(script_path)]
        if script.endswith(".tsx") or script.endswith(".js"):
            return ["node", str(script_path)]
        return ["bash", str(script_path)]

    def _audit_log(self, skill: str, script: str, args: str, event: str, exit_code: int | None = None) -> None:
        log_path = get_settings().skills_dir.parent / "exec_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skill": skill,
            "script": script,
            "args": args,
            "event": event,
        }
        if exit_code is not None:
            entry["exit_code"] = exit_code
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
