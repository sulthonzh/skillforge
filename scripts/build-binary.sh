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
