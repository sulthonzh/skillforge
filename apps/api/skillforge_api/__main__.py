"""Frozen-runtime entry point.

When SkillForge is packaged as a single executable (PyInstaller), running
``./skillforge`` with no arguments should just start the app. This entry point
makes ``serve`` the implicit default command when none is supplied, then
delegates to the full Typer CLI.

It is also runnable unfrozen via ``python -m skillforge_api``.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Default to the offline mock provider so the binary works with zero config.
    os.environ.setdefault("SKILLFORGE_AI_PROVIDER", "mock")

    args = sys.argv[1:]

    # Bare invocation → behave as `serve`. (Typer's no_args_is_help would show
    # help instead; we want "just run".)
    if not args:
        args = ["serve"]

    from skillforge_cli.main import app

    app(args, standalone_mode=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
