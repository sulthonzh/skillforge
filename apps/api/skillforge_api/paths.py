"""Runtime path resolution.

Works both in a normal (editable-installed) checkout and inside a PyInstaller
frozen binary. PyInstaller extracts bundled data files to ``sys._MEIPASS`` at
startup; this module exposes helpers that find them there first, then fall back
to the repo layout.

Why this exists: the Jinja2 templates and ``tool_catalog.yaml`` live *inside*
the ``skillforge_api`` package and are loaded via ``importlib.resources`` (which
PyInstaller handles automatically). The Web UI export, however, is bundled as
loose data (``--add-data apps/web/out``) at a known location relative to
``_MEIPASS``, so it needs an explicit lookup.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller-built executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


@lru_cache(maxsize=1)
def bundle_root() -> Path:
    """Root of the bundled data tree.

    In a frozen build this is ``sys._MEIPASS`` (PyInstaller's temp dir). In a
    normal install it's the directory that contains the ``apps/`` tree, so the
    same relative paths (``apps/web/out``) resolve either way.
    """
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # Repo layout: <root>/apps/api/skillforge_api/paths.py  ->  <root>
    here = Path(__file__).resolve()
    api_pkg = here.parents[1]              # .../apps/api
    if api_pkg.name == "api":
        return api_pkg.parent              # .../apps  (sibling of cli/, web/)
    return here.parent


@lru_cache(maxsize=1)
def web_export_dir() -> Path | None:
    """Locate the bundled Web UI export, or ``None`` if not bundled.

    Lookup order:
      1. ``$SKILLFORGE_WEB_DIR`` (explicit override — wins everywhere).
      2. ``apps/web/out`` under the bundle root (frozen: MEIPASS; dev: repo).
      3. ``web/out`` under the bundle root (flat frozen layout).
    """
    override = os.environ.get("SKILLFORGE_WEB_DIR")
    if override:
        p = Path(override).expanduser().resolve()
        return p if (p / "index.html").is_file() else None

    root = bundle_root()
    candidates = [
        root / "apps" / "web" / "out",
        root / "web" / "out",
        root / "out",
    ]
    for c in candidates:
        if (c / "index.html").is_file():
            return c
    return None
