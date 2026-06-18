# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the SkillForge single-binary build.
#
# Usage (from repo root):
#   ./scripts/build-binary.sh
# or manually:
#   pyinstaller scripts/skillforge.spec --noconfirm --distpath dist --workpath build
#
# Produces dist/skillforge — a standalone executable that serves the API and the
# bundled Web UI on one port with zero Python/Node install on the target.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# repo root = parent of the scripts/ dir that holds this spec when invoked as
# scripts/skillforge.spec; PyInstaller runs with cwd == repo root.
REPO = Path.cwd()

# --- collect all submodules of our own packages + heavy libs ---
hiddenimports = []
hiddenimports += collect_submodules("skillforge_api")
hiddenimports += collect_submodules("skillforge_cli")
hiddenimports += collect_submodules("sqlalchemy")
hiddenimports += [
    # SQLModel/SQLAlchemy SQLite wiring (not always auto-detected).
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    # Pydantic v2 internals.
    "pydantic",
    "pydantic.deprecated.decorator",
    "pydantic._internal._validators",
    # Jinja2 / yaml are top-level imports but be explicit.
    "jinja2",
    "yaml",
    # uvicorn server bits the CLI imports lazily.
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

# --- data files ---
datas = []

# Package-internal data: Jinja2 templates + tool catalog. PyInstaller does not
# collect non-.py files inside a package automatically, so bundle them at the
# same relative path the package expects (skillforge_api/templates, .../data).
api_pkg = REPO / "apps" / "api" / "skillforge_api"
for subdir in ("templates", "data"):
    src = api_pkg / subdir
    if src.is_dir():
        datas.append((str(src), str(Path("skillforge_api") / subdir)))
    else:
        raise SystemExit(f"{src} not found; cannot bundle {subdir}/")

# Web UI export → bundled at apps/web/out (matches paths.web_export_dir).
web_out = REPO / "apps" / "web" / "out"
if web_out.is_dir():
    # PyInstaller copies the tree into the bundle root under apps/web/out.
    datas.append((str(web_out), str(Path("apps/web/out"))))
else:
    raise SystemExit(
        "apps/web/out not found. Run `npm run build` in apps/web first "
        "(or scripts/build-binary.sh, which does it for you)."
    )

a = Analysis(
    [str(REPO / "apps/api/skillforge_api/__main__.py")],
    pathex=[
        str(REPO),                      # so `import skillforge_api` resolves
        str(REPO / "apps" / "api"),
        str(REPO / "apps" / "cli"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ---- pkg_resources / setuptools ----
        # SkillForge never imports pkg_resources at runtime, but PyInstaller's
        # pyi_rth_pkgres runtime hook runs unconditionally and on setuptools
        # >=70 it tries to import the split-out jaraco.* submodules (jaraco.text,
        # jaraco.functools, ...). If jaraco isn't bundled the binary crashes at
        # startup with ModuleNotFoundError: No module named 'jaraco.text'.
        # Excluding all three means the runtime hook has nothing to load, and
        # since nothing in the app needs it, the binary just works.
        "pkg_resources",
        "setuptools",
        "jaraco",
        "jaraco.text",
        "jaraco.functools",
        "jaraco.context",
        # ---- Trim test/tooling we don't need at runtime ----
        "pytest",
        "tests",
        "pip",
        "distutils",
        # ---- Heavy packages SkillForge never imports ----
        # These are listed explicitly so a build environment that happens to
        # have them installed (e.g. a shared/global site-packages) cannot bloat
        # the binary. Each has been verified absent from the import graph.
        # AWS SDK (~12 MB) — we don't talk to AWS.
        "botocore",
        "boto3",
        "s3transfer",
        # Numeric / plotting (~16 MB combined) — we don't compute or plot.
        "numpy",
        "matplotlib",
        "pandas",
        "scipy",
        "PIL",
        "Pillow",
        "contourpy",
        # DB drivers for engines we don't use (we use SQLite via sqlite3).
        "psycopg2",
        "psycopg",
        "asyncpg",
        "pymysql",
        "cryptography",  # only needed by some DB/SSH drivers
        # XML parsing — unused (we use stdlib xml + yaml).
        "lxml",
        # IDE / notebook tooling — unused.
        "jedi",
        "IPython",
        "jupyter",
        "notebook",
        "tornado",
        "zmq",
        # Parquet / arrow — unused.
        "pyarrow",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="skillforge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # keep stdout for `serve` logs + CLI output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
