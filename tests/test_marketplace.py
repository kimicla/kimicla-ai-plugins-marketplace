"""Offline tests of marketplace manifests, read restrictions, and all API payloads."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fake_fastmcp = types.ModuleType("fastmcp")
class FakeFastMCP:
    def __init__(self, name): self.name = name
    def tool(self, fn): return fn
fake_fastmcp.FastMCP = FakeFastMCP
sys.modules.setdefault("fastmcp", fake_fastmcp)


def import_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ocr = import_module("local_ocr", ROOT / "plugins/local-ocr/server.py")
qwen = import_module("local_qwen", ROOT / "plugins/local-qwen/server.py")


class MarketplaceTests(unittest.TestCase):
    def test_manifests_and_scripts(self):
        catalog = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(catalog["name"], "kimicla-ai-plugins")
        self.assertEqual(len(catalog["plugins"]), 3)
        for entry in catalog["plugins"]:
            folder = (ROOT / entry["source"]).resolve()
            self.assertTrue(folder.is_relative_to(ROOT))
            manifest = json.loads((folder / ".claude-plugin/plugin.json").read_text())
            self.assertEqual(entry["name"], manifest["name"])
            self.assertEqual(entry["version"], manifest["version"])
            if (folder / ".mcp.json").exists():
                config = json.loads((folder / ".mcp.json").read_text())
                self.assertEqual(len(config["mcpServers"]), 1)
                self.assertTrue((folder / "scripts/start.sh").is_file())

    def test_read_scope(self):
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            root = Path(allowed)
            (root / "sample.png").write_bytes(b"png")
            (root / "symlink.pdf").symlink_to(Path(outside) / "not_here.pdf")
            with patch.dict(os.environ, {"LOCAL_AI_ALLOWED_DIR": allowed}):
                self.assertEqual(ocr.validate_file("sample.png"), root / "sample.png")
                with self.assertRaises(ValueError): ocr.validate_file("symlink.pdf")
                with self.assertRaises(ValueError): ocr.validate_file("../abc.png")
                with patch.object(ocr, "ocr_image", return_value="test"):
                    self.assertIn("test", ocr.ocr_file("sample.png"))

    def test_pdf_page_ranges(self):
        self.assertEqual(ocr.parse_pages("1-3,5", 10), [1, 2, 3, 5])
        with self.assertRaises(ValueError): ocr.parse_pages("1-99", 100)
        with self.assertRaises(ValueError): ocr.parse_pages("../3", 10)
        with self.assertRaises(ValueError): ocr.parse_pages("8", 3)

    def test_gateway_defaults(self):
        keys = ["LOCAL_AI_BASE_URL", "LOCAL_AI_API_STYLE", "LOCAL_OCR_MODEL",
                "LOCAL_QWEN_MODEL", "LOCAL_AI_API_KEY", "ANTHROPIC_BASE_URL",
                "ANTHROPIC_AUTH_TOKEN"]
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ocr.config()[:3], ("http://127.0.0.1:8080", "anthropic", "GLM-OCR-4bit"))
            self.assertEqual(qwen.config()[2], "Qwen3-8-27B-4bit")
        with patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "http://localhost:8080"}):
            self.assertEqual(ocr.config()[0], "http://localhost:8080")

    def test_anthropic_ocr_image_payload(self):
        with patch.dict(os.environ, {"LOCAL_AI_BASE_URL": "http://localhost:8080",
                                  "LOCAL_AI_API_STYLE": "anthropic", "LOCAL_OCR_MODEL": "GLM-OCR-4bit"}):
            def fake(url, payload, headers):
                self.assertEqual(url, "http://localhost:8080/v1/messages")
                self.assertEqual(payload["model"], "GLM-OCR-4bit")
                self.assertEqual(payload["messages"][0]["content"][1]["type"], "image")
                self.assertEqual(payload["messages"][0]["content"][1]["source"]["media_type"], "image/jpeg")
                return {"content": [{"type": "text", "text": "识别成功"}]}
            with patch.object(ocr, "post_json", side_effect=fake):
                self.assertEqual(ocr.ocr_image("Text Recognition:", b"jpg", "image/jpeg"), "识别成功")

    def test_other_ocr_api_formats(self):
        responses = {"openai": {"choices": [{"message": {"content": "ok"}}]},
                     "responses": {"output": [{"content": [{"type": "output_text", "text": "ok"}]}]},
                     "ollama": {"response": "ok"}}
        for style, mock in responses.items():
            with self.subTest(style=style), patch.dict(os.environ, {"LOCAL_AI_API_STYLE": style}):
                with patch.object(ocr, "post_json", return_value=mock) as call:
                    self.assertEqual(ocr.ocr_image("Read:", b"image"), "ok")
                    expected = {"openai": "/v1/chat/completions", "responses": "/v1/responses",
                                "ollama": "/api/generate"}[style]
                    self.assertTrue(call.call_args.args[0].endswith(expected))

    def test_qwen_api(self):
        with patch.dict(os.environ, {"LOCAL_AI_API_STYLE": "anthropic"}):
            with patch.object(qwen, "post_json", return_value={"content": [{"type": "text", "text": "review"}]}) as req:
                self.assertIn("review", qwen.ask_local_qwen("Find issues", "context"))
                self.assertIn("Reference material", req.call_args.args[1]["messages"][0]["content"])
        with self.assertRaises(ValueError): qwen.ask_local_qwen("  ")


if __name__ == "__main__":
    unittest.main()
