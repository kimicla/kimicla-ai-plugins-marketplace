#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Claude Code started from an IDE may not have Homebrew paths in PATH.
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  for candidate in /opt/homebrew/bin/uv /usr/local/bin/uv "$HOME/.local/bin/uv"; do
    if [[ -x "$candidate" ]]; then UV_BIN="$candidate"; break; fi
  done
fi
if [[ -z "$UV_BIN" ]]; then
  echo 'local-ocr: uv not found; install with: brew install uv' >&2
  exit 127
fi
exec "$UV_BIN" run --no-project --with 'fastmcp>=2,<5' --with 'pypdfium2>=5,<6' --with 'Pillow>=11,<13' python "$HERE/server.py"
