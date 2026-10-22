#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v uv >/dev/null 2>&1; then
  echo 'local-ocr: uv is required; install with: brew install uv' >&2
  exit 127
fi
exec uv run --no-project --with 'fastmcp>=2,<5' --with 'pypdfium2>=5,<6' --with 'Pillow>=11,<13' python "$HERE/server.py"
