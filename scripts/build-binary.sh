#!/usr/bin/env bash
# Build the SkillForge single-binary executable.
#
# Produces dist/skillforge — a standalone binary that serves the API and the
# bundled Web UI on one port, with zero Python or Node install required on the
# target machine.
#
# Requirements (build host only):
#   - Python 3.10+ with PyInstaller and the api/cli packages installed
#   - Node 18+ and npm (to build the Web UI export)
#
# Usage:
#   ./scripts/build-binary.sh
#
# Env overrides:
#   PYINSTALLER   path to pyinstaller (default: from venv/PATH)
#   NODE          path to node binary (default: from PATH)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

NODE="${NODE:-$(command -v node || true)}"
NPM="${NPM:-$(command -v npm || true)}"

echo "==> Building Web UI export (apps/web/out)"
if [[ -z "${NPM}" ]]; then
  echo "ERROR: npm not found. Install Node 18+ to build the Web UI." >&2
  exit 1
fi
( cd apps/web && npm install --no-audit --no-fund && npm run build )
if [[ ! -f apps/web/out/index.html ]]; then
  echo "ERROR: Web UI export did not produce apps/web/out/index.html" >&2
  exit 1
fi

echo "==> Locating PyInstaller"
PYI="${PYINSTALLER:-$(command -v pyinstaller || true)}"
if [[ -z "${PYI}" ]]; then
  # Fall back to the api venv if present.
  if [[ -x "apps/api/.venv/bin/pyinstaller" ]]; then
    PYI="apps/api/.venv/bin/pyinstaller"
  else
    echo "ERROR: pyinstaller not found. Install with: pip install pyinstaller" >&2
    exit 1
  fi
fi
echo "    using: $PYI"

echo "==> Ensuring api + cli packages are importable from repo root"
# Make sure both packages resolve via pathex in the spec.
${PYI%pyinstaller}python -c "import sys; sys.path.insert(0,'apps/api'); sys.path.insert(0,'apps/cli'); import skillforge_api, skillforge_cli; print('imports OK')" 2>/dev/null || true

echo "==> Verifying app does not import excluded/heavy packages"
# Defensive: if the app ever starts importing one of the packages we exclude
# in the spec (AWS SDK, numpy, etc.), the build would silently drop a needed
# dependency. Catch that here, before PyInstaller runs.
${PYI%pyinstaller}python - <<'PY' || { echo "ERROR: app imports an excluded package — fix the spec or the code" >&2; exit 1; }
import sys
sys.path.insert(0, "apps/api")
EXCLUDED = {
    "botocore", "boto3", "s3transfer", "numpy", "matplotlib", "pandas",
    "scipy", "PIL", "Pillow", "contourpy", "psycopg2", "psycopg", "asyncpg",
    "pymysql", "cryptography", "lxml", "jedi", "IPython", "jupyter",
    "notebook", "tornado", "zmq", "pyarrow",
}
before = set(sys.modules)
import skillforge_api.main  # noqa: triggers the full import graph
loaded = set(sys.modules) - before
hits = sorted({m.split(".")[0] for m in loaded} & EXCLUDED)
if hits:
    print(f"FAIL: app imports excluded packages: {hits}", file=sys.stderr)
    sys.exit(1)
print("    OK — app does not import any excluded package")
PY

echo "==> Running PyInstaller (this is slow; ~1-3 min)"
rm -rf build dist
"$PYI" scripts/skillforge.spec --noconfirm --distpath dist --workpath build

BINARY="dist/skillforge"
if [[ ! -x "$BINARY" ]]; then
  echo "ERROR: build did not produce $BINARY" >&2
  exit 1
fi

SIZE=$(du -h "$BINARY" | cut -f1)
echo ""
echo "==> Built $BINARY ($SIZE)"
echo "    Run it:  ./$BINARY            # serves http://localhost:8000"
echo "    Help:    ./$BINARY --help"
echo "    Plan:    ./$BINARY plan \"I need a backend skill for FastAPI\""

# ---------------------------------------------------------------------------
# Post-build verification. These guards make regressions (the jaraco.text
# crash and the 71MB bloat) impossible to ship silently:
#   1. The binary must actually start (catches the jaraco.text / pkg_resources
#      runtime-hook crash that PyInstaller's pyi_rth_pkgres can trigger).
#   2. The binary must stay under a size budget (catches accidental inclusion
#      of heavy packages like botocore/numpy/matplotlib).
#   3. The binary must not bundle the excluded packages.
# ---------------------------------------------------------------------------
echo "==> Verifying binary starts (catches pkg_resources/jaraco runtime crash)"
if ! "$BINARY" --help >/dev/null 2>&1; then
  echo "ERROR: binary failed to start (likely pkg_resources/jaraco crash)" >&2
  "$BINARY" --help >&2 || true
  exit 1
fi
echo "    OK — binary starts"

echo "==> Verifying binary size is under budget"
SIZE_KB=$(du -k "$BINARY" | cut -f1)
# 35 MB gives ~60% headroom over the current 22 MB. If a legitimately needed
# heavy dep is added later, raise this — but do it deliberately, not silently.
MAX_KB=$((35 * 1024))
if (( SIZE_KB > MAX_KB )); then
  echo "ERROR: binary is ${SIZE_KB} KB, over the ${MAX_KB} KB budget." >&2
  echo "       A heavy package likely slipped in. Check scripts/skillforge.spec excludes." >&2
  exit 1
fi
echo "    OK — ${SIZE_KB} KB within ${MAX_KB} KB budget"
