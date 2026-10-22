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
# Trust the platform certificate store (including corporate root CAs) when
# resolving Python dependencies. Can be overridden with UV_SYSTEM_CERTS=false.
export UV_SYSTEM_CERTS="${UV_SYSTEM_CERTS:-true}"
# Ignore an old pyenv 3.9 selected in the invoking shell; use Python >=3.10.
exec "$UV_BIN" run --python '>=3.10' --no-project --with 'fastmcp>=2,<5' --with 'pypdfium2>=5,<6' --with 'Pillow>=11,<13' python "$HERE/server.py"
