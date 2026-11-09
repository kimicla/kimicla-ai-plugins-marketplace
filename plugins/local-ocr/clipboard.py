"""Local clipboard OCR runner for the user-invoked Claude Code Skill.

Reads an image from the macOS clipboard and sends it only to an explicitly
configured loopback inference server. Prints OCR text (no image) to stdout.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import server


def validate_local_route() -> str:
    settings = server.claude_settings_env()

    def value(key: str) -> str:
        return os.environ.get(key) or settings.get(key, "")

    if not any(value(key) for key in
               ("LOCAL_BASE_URL", "LOCAL_OCR_BASE_URL", "LOCAL_AI_BASE_URL")):
        raise RuntimeError(
            "Set LOCAL_BASE_URL=http://127.0.0.1:8080 in Claude Code "
            "settings before clipboard OCR. Refusing main-model fallback."
        )

    base, _, _, _ = server.config()
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
        "localhost", "127.0.0.1", "::1"
    ):
        raise RuntimeError(
            "Clipboard OCR requires a loopback LOCAL_BASE_URL; "
            "refusing to send images to a remote model endpoint."
        )
    return base


def read_clipboard() -> bytes:
    if sys.platform != "darwin":
        raise RuntimeError("Clipboard image capture is supported on macOS only.")
    source = Path(__file__).parent / "scripts" / "clipboard.swift"
    try:
        proc = subprocess.run(
            ["swift", str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Swift is unavailable. Install Apple Command Line Tools."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("macOS clipboard image capture timed out.") from exc
    if proc.returncode != 0:
        details = proc.stderr.decode("utf-8", "replace").strip()[-1200:]
        raise RuntimeError(details or "Clipboard image capture failed.")
    if not 0 < len(proc.stdout) <= server.MAX_BYTES:
        raise RuntimeError("Clipboard image is empty or exceeds 25MB.")
    return proc.stdout


def transcribe() -> str:
    validate_local_route()  # Must run before reading potentially sensitive data.
    image = read_clipboard()
    text = server.ocr_image("Text Recognition:", image, "image/png")
    if not text.strip():
        raise RuntimeError("Local OCR returned no text.")
    return text[:16000]


if __name__ == "__main__":
    try:
        print(transcribe())
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"local-ocr clipboard error: {exc}", file=sys.stderr)
        sys.exit(2)
